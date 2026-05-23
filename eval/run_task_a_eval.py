"""Task A evaluation script using real ChromaDB test samples."""

from dotenv import load_dotenv

load_dotenv(override=True)

import argparse
import csv
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import chromadb
import numpy as np
import requests
from bert_score import score as bert_score
from rouge_score import rouge_scorer
from sklearn.metrics import mean_absolute_error, mean_squared_error

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(name)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:8001"
DEFAULT_LIMIT = 30
DEFAULT_TIMEOUT = 60
RETRY_WAIT_SECONDS = 35
PLATFORM_PREFIXES = ("yelp", "amazon", "goodreads")


@dataclass(slots=True)
class TestSample:
    """Single real evaluation sample loaded from ChromaDB."""

    sample_id: str
    user_id: str
    platform: str
    item_id: str
    item_name: str
    item_category: str
    reference_review: str
    actual_rating: float


@dataclass(slots=True)
class EvalResult:
    """Per-sample evaluation result."""

    sample_id: str
    user_id: str
    platform: str
    item_id: str
    generated_review: str
    predicted_rating: float
    reference_review: str
    actual_rating: float
    rouge1: float
    rougeL: float
    bertscore_f1: float | None


@dataclass(slots=True)
class AggregateMetrics:
    """Aggregate metrics across all successful Task A samples."""

    num_samples: int
    rouge1_mean: float
    rouge1_std: float
    rougeL_mean: float
    rougeL_std: float
    bertscore_f1_mean: float | None
    bertscore_f1_std: float | None
    rmse: float
    mae: float


def parse_args() -> argparse.Namespace:
    """Parses CLI arguments."""
    parser = argparse.ArgumentParser(description="Evaluate Task A using real ChromaDB test reviews.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Maximum number of test samples to evaluate.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base URL for the Task A service.")
    parser.add_argument(
        "--skip-bert",
        action="store_true",
        help="Skip BERTScore computation to avoid slow model downloads.",
    )
    return parser.parse_args()


def project_root() -> Path:
    """Returns the repository root from the eval module path."""
    return Path(__file__).resolve().parent.parent


def normalize_id(value: str) -> str:
    """Strips known platform prefixes to improve cross-collection matching."""
    normalized = str(value or "").strip()
    for prefix in PLATFORM_PREFIXES:
        token = f"{prefix}_"
        if normalized.startswith(token):
            return normalized[len(token) :].lstrip("_")
    return normalized


def build_id_candidates(value: str, platform: str | None = None) -> list[str]:
    """Builds a small set of candidate IDs with and without platform prefixes."""
    candidates: list[str] = []
    raw = str(value or "").strip()
    core = normalize_id(raw)

    for candidate in (raw, core):
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    if platform and core:
        prefixed = f"{platform}_{core}"
        if prefixed not in candidates:
            candidates.append(prefixed)

    if core:
        for prefix in PLATFORM_PREFIXES:
            prefixed = f"{prefix}_{core}"
            if prefixed not in candidates:
                candidates.append(prefixed)

    return candidates


def safe_float(value: Any, default: float = 0.0) -> float:
    """Converts a value to float with a safe fallback."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def request_with_retry(method: str, url: str, **kwargs: Any) -> requests.Response:
    """Executes an HTTP request and retries once on rate limiting."""
    response = requests.request(method, url, **kwargs)
    if response.status_code == 429:
        logger.warning("Rate limit hit, waiting %ss...", RETRY_WAIT_SECONDS)
        time.sleep(RETRY_WAIT_SECONDS)
        response = requests.request(method, url, **kwargs)
    return response


def check_connection(base_url: str) -> None:
    """Fails fast when the Task A service is unavailable."""
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        response.raise_for_status()
        print(f"Connected to Task A at {base_url}")
    except Exception:
        print(f"ERROR: Cannot connect to Task A at {base_url}")
        print("Start it with: uvicorn task_a.main:app --port 8001")
        print("Or if using Docker: docker compose up task_a")
        sys.exit(1)


def get_collections() -> tuple[Any, Any]:
    """Creates a Chroma client and returns the reviews and items collections."""
    chroma_path = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
    client = chromadb.PersistentClient(path=chroma_path)
    return client.get_collection("reviews"), client.get_collection("items")


def get_item_name(item_id: str, platform: str, items_col: Any) -> tuple[str, str]:
    """Returns `(name, category)` for an item ID using a few safe lookup variants."""
    for candidate in build_id_candidates(item_id, platform=platform):
        try:
            result = items_col.get(ids=[candidate])
        except Exception:
            continue

        ids = result.get("ids") or []
        if not ids:
            continue

        metadata = ((result.get("metadatas") or [None])[0] or {})
        return (
            str(metadata.get("name") or candidate),
            str(metadata.get("category") or "General"),
        )

    return item_id, "General"


def load_test_samples(limit: int) -> list[TestSample]:
    """Loads real test reviews from ChromaDB."""
    reviews_col, items_col = get_collections()
    all_reviews = reviews_col.get(limit=max(1000, limit))

    ids = all_reviews.get("ids") or []
    documents = all_reviews.get("documents") or []
    metadatas = all_reviews.get("metadatas") or []

    test_indices = [
        index
        for index, metadata in enumerate(metadatas)
        if (metadata or {}).get("is_test_split") == "true"
    ]

    samples: list[TestSample] = []
    for index in test_indices[:limit]:
        metadata = metadatas[index] or {}
        user_id = str(metadata.get("user_id") or "").strip()
        item_id = str(metadata.get("item_id") or "").strip()
        platform = str(metadata.get("platform") or "yelp").strip() or "yelp"
        reference_review = str(documents[index] or "").strip()

        if not user_id or not item_id or not reference_review:
            logger.warning("Skipping incomplete review sample at index %s", index)
            continue

        item_name, item_category = get_item_name(item_id, platform, items_col)
        samples.append(
            TestSample(
                sample_id=str(ids[index] or f"review_{index}"),
                user_id=user_id,
                platform=platform,
                item_id=item_id,
                item_name=item_name,
                item_category=item_category,
                reference_review=reference_review,
                actual_rating=safe_float(metadata.get("rating"), 3.0),
            )
        )

    return samples


def build_payload(sample: TestSample) -> dict[str, Any]:
    """Builds the confirmed Task A request payload shape."""
    return {
        "user_persona": {
            "user_id": sample.user_id,
            "platform": sample.platform,
            "review_history": [],
            "preferences": {},
        },
        "item_details": {
            "item_id": sample.item_id,
            "name": sample.item_name,
            "category": sample.item_category,
            "attributes": {},
        },
        "nigerian_mode": False,
        "nigerian_intensity": "medium",
    }


def call_task_a(base_url: str, sample: TestSample) -> tuple[str, float] | None:
    """Calls the Task A endpoint and returns generated review text and rating."""
    payload = build_payload(sample)
    response = request_with_retry(
        "post",
        f"{base_url}/generate-review",
        json=payload,
        timeout=DEFAULT_TIMEOUT,
    )

    if not response.ok:
        logger.error(
            "Task A request failed for sample %s with status %s: %s",
            sample.sample_id,
            response.status_code,
            response.text[:500],
        )
        return None

    try:
        data = response.json()
    except ValueError:
        logger.error("Task A returned non-JSON response for sample %s", sample.sample_id)
        return None

    generated_review = str(data.get("review_text") or "").strip()
    if not generated_review:
        logger.error("Task A response missing `review_text` for sample %s", sample.sample_id)
        return None

    predicted_rating = safe_float(data.get("rating"), sample.actual_rating)
    return generated_review, predicted_rating


def compute_rouge_scores(reference_review: str, generated_review: str) -> tuple[float, float]:
    """Computes ROUGE-1 and ROUGE-L F1 for a single sample."""
    scorer = rouge_scorer.RougeScorer(["rouge1", "rougeL"], use_stemmer=True)
    scores = scorer.score(reference_review, generated_review)
    return scores["rouge1"].fmeasure, scores["rougeL"].fmeasure


def apply_bertscore(results: list[EvalResult]) -> None:
    """Computes BERTScore in one batch and writes it back into each result."""
    if not results:
        return

    _, _, f1_scores = bert_score(
        [result.generated_review for result in results],
        [result.reference_review for result in results],
        lang="en",
        verbose=False,
    )
    for result, score in zip(results, f1_scores, strict=False):
        result.bertscore_f1 = float(score.item())


def compute_aggregate_metrics(results: list[EvalResult]) -> AggregateMetrics:
    """Computes aggregate metrics over successful evaluation results."""
    if not results:
        return AggregateMetrics(
            num_samples=0,
            rouge1_mean=0.0,
            rouge1_std=0.0,
            rougeL_mean=0.0,
            rougeL_std=0.0,
            bertscore_f1_mean=None,
            bertscore_f1_std=None,
            rmse=0.0,
            mae=0.0,
        )

    rouge1_scores = np.array([result.rouge1 for result in results], dtype=float)
    rougeL_scores = np.array([result.rougeL for result in results], dtype=float)
    actual_ratings = np.array([result.actual_rating for result in results], dtype=float)
    predicted_ratings = np.array([result.predicted_rating for result in results], dtype=float)
    bert_scores = [result.bertscore_f1 for result in results if result.bertscore_f1 is not None]

    return AggregateMetrics(
        num_samples=len(results),
        rouge1_mean=float(np.mean(rouge1_scores)),
        rouge1_std=float(np.std(rouge1_scores)),
        rougeL_mean=float(np.mean(rougeL_scores)),
        rougeL_std=float(np.std(rougeL_scores)),
        bertscore_f1_mean=float(np.mean(bert_scores)) if bert_scores else None,
        bertscore_f1_std=float(np.std(bert_scores)) if bert_scores else None,
        rmse=float(np.sqrt(mean_squared_error(actual_ratings, predicted_ratings))),
        mae=float(mean_absolute_error(actual_ratings, predicted_ratings)),
    )


def print_results_table(metrics: AggregateMetrics, skip_bert: bool) -> None:
    """Prints a compact summary table for Task A evaluation."""
    print("\n" + "=" * 40)
    print("TASK A EVALUATION RESULTS")
    print("=" * 40)
    print(f"Samples evaluated: {metrics.num_samples}")
    print("")
    print("Text Quality:")
    print(f"  ROUGE-1 Mean:  {metrics.rouge1_mean:.4f}")
    print(f"  ROUGE-1 Std:   {metrics.rouge1_std:.4f}")
    print(f"  ROUGE-L Mean:  {metrics.rougeL_mean:.4f}")
    print(f"  ROUGE-L Std:   {metrics.rougeL_std:.4f}")
    if skip_bert:
        print("  BERTScore-F1:  skipped")
    else:
        mean_value = 0.0 if metrics.bertscore_f1_mean is None else metrics.bertscore_f1_mean
        std_value = 0.0 if metrics.bertscore_f1_std is None else metrics.bertscore_f1_std
        print(f"  BERTScore-F1 Mean: {mean_value:.4f}")
        print(f"  BERTScore-F1 Std:  {std_value:.4f}")
    print("")
    print("Rating Accuracy:")
    print(f"  RMSE:          {metrics.rmse:.4f}")
    print(f"  MAE:           {metrics.mae:.4f}")


def save_results(results: list[EvalResult], metrics: AggregateMetrics, skip_bert: bool) -> None:
    """Writes JSON and CSV outputs for Task A evaluation."""
    eval_dir = project_root() / "eval"
    json_path = eval_dir / "eval_results_task_a.json"
    csv_path = eval_dir / "eval_results_task_a.csv"

    output_data = {
        "aggregate_metrics": asdict(metrics),
        "skip_bert": skip_bert,
        "sample_results": [asdict(result) for result in results],
    }

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(output_data, file, indent=2)

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "sample_id",
                "user_id",
                "platform",
                "item_id",
                "predicted_rating",
                "actual_rating",
                "rouge1",
                "rougeL",
                "bertscore_f1",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "sample_id": result.sample_id,
                    "user_id": result.user_id,
                    "platform": result.platform,
                    "item_id": result.item_id,
                    "predicted_rating": result.predicted_rating,
                    "actual_rating": result.actual_rating,
                    "rouge1": result.rouge1,
                    "rougeL": result.rougeL,
                    "bertscore_f1": result.bertscore_f1,
                }
            )

    logger.info("Results saved to %s and %s", json_path, csv_path)


def main() -> None:
    """Runs the full Task A evaluation flow."""
    args = parse_args()
    limit = max(1, min(args.limit, DEFAULT_LIMIT))

    check_connection(args.base_url)
    samples = load_test_samples(limit)
    if not samples:
        logger.error("No real Task A test samples were loaded from ChromaDB.")
        sys.exit(1)

    logger.info("Loaded %s real Task A test samples from ChromaDB", len(samples))
    results: list[EvalResult] = []

    for index, sample in enumerate(samples, start=1):
        print(f"Evaluating sample {index}/{len(samples)}...")
        response = call_task_a(args.base_url, sample)
        if response is None:
            continue

        generated_review, predicted_rating = response
        rouge1, rougeL = compute_rouge_scores(sample.reference_review, generated_review)
        results.append(
            EvalResult(
                sample_id=sample.sample_id,
                user_id=sample.user_id,
                platform=sample.platform,
                item_id=sample.item_id,
                generated_review=generated_review,
                predicted_rating=predicted_rating,
                reference_review=sample.reference_review,
                actual_rating=sample.actual_rating,
                rouge1=rouge1,
                rougeL=rougeL,
                bertscore_f1=None,
            )
        )

    if not results:
        logger.error("Task A evaluation produced no successful results.")
        sys.exit(1)

    if not args.skip_bert:
        print(f"Computing BERTScore for {len(results)} samples...")
        apply_bertscore(results)

    metrics = compute_aggregate_metrics(results)
    print_results_table(metrics, skip_bert=args.skip_bert)
    save_results(results, metrics, skip_bert=args.skip_bert)


if __name__ == "__main__":
    main()
