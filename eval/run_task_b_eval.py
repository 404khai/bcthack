"""Task B evaluation script using real ChromaDB users and held-out reviews."""

from dotenv import load_dotenv

load_dotenv(override=True)

import argparse
import json
import logging
import math
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import chromadb
import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(name)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:8002"
DEFAULT_LIMIT = 20
DEFAULT_TIMEOUT = 60
RETRY_WAIT_SECONDS = 35
PLATFORM_PREFIXES = ("yelp", "amazon", "goodreads")


@dataclass(slots=True)
class TestUser:
    """Real Task B evaluation user loaded from ChromaDB."""

    user_id: str
    platform: str
    review_count: int
    held_out_items: list[str]
    metadata: dict[str, Any]
    is_cold_start: bool


@dataclass(slots=True)
class RecommendationResult:
    """Recommendation payload captured from the Task B endpoint."""

    user_id: str
    platform: str
    review_count: int
    held_out_items: list[str]
    recommended_items: list[str]
    scores: list[float]
    explanations: list[str]
    thinking: list[str]
    is_cold_start: bool
    ndcg_at_10: float
    hit_rate_at_10: float


@dataclass(slots=True)
class EvaluationMetrics:
    """Aggregate ranking metrics for Task B evaluation."""

    users_evaluated: int
    warm_users: int
    cold_users: int
    overall_ndcg_at_10: float
    overall_hit_rate_at_10: float
    warm_ndcg_at_10: float
    warm_hit_rate_at_10: float
    cold_ndcg_at_10: float
    cold_hit_rate_at_10: float


def parse_args() -> argparse.Namespace:
    """Parses CLI arguments."""
    parser = argparse.ArgumentParser(description="Evaluate Task B using real ChromaDB users.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Maximum number of users to evaluate.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base URL for the Task B service.")
    return parser.parse_args()


def project_root() -> Path:
    """Returns the repository root from the eval module path."""
    return Path(__file__).resolve().parent.parent


def normalize_id(value: str) -> str:
    """Strips known platform prefixes to improve ID matching."""
    normalized = str(value or "").strip()
    for prefix in PLATFORM_PREFIXES:
        token = f"{prefix}_"
        if normalized.startswith(token):
            return normalized[len(token) :].lstrip("_")
    return normalized


def build_id_candidates(value: str) -> list[str]:
    """Generates candidate IDs with and without platform prefixes."""
    candidates: list[str] = []
    raw = str(value or "").strip()
    core = normalize_id(raw)

    for candidate in (raw, core):
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    if core:
        for prefix in PLATFORM_PREFIXES:
            prefixed = f"{prefix}_{core}"
            if prefixed not in candidates:
                candidates.append(prefixed)

    return candidates


def safe_int(value: Any, default: int = 0) -> int:
    """Converts a value to int with a fallback."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Converts a value to float with a fallback."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def request_with_retry(method: str, url: str, **kwargs: Any) -> requests.Response:
    """Executes an HTTP request and retries once on HTTP 429."""
    response = requests.request(method, url, **kwargs)
    if response.status_code == 429:
        logger.warning("Rate limit hit, waiting %ss...", RETRY_WAIT_SECONDS)
        time.sleep(RETRY_WAIT_SECONDS)
        response = requests.request(method, url, **kwargs)
    return response


def check_connection(base_url: str) -> None:
    """Fails fast if the Task B service is unavailable."""
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        response.raise_for_status()
        print(f"Connected to Task B at {base_url}")
    except Exception:
        print(f"ERROR: Cannot connect to Task B at {base_url}")
        print("Start it with: uvicorn task_b.main:app --port 8002")
        print("Or if using Docker: docker compose up task_b")
        sys.exit(1)


def get_collections() -> tuple[Any, Any]:
    """Creates the Chroma client and returns users and reviews collections."""
    chroma_path = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
    client = chromadb.PersistentClient(path=chroma_path)
    return client.get_collection("users"), client.get_collection("reviews")


def get_held_out_items(user_id: str, reviews_col: Any) -> list[str]:
    """Returns normalized held-out item IDs for a user from the test split."""
    held_out: list[str] = []
    for candidate in build_id_candidates(user_id):
        try:
            results = reviews_col.get(where={"user_id": candidate}, limit=50)
        except Exception:
            continue

        for metadata in results.get("metadatas") or []:
            meta = metadata or {}
            item_id = str(meta.get("item_id") or "").strip()
            if meta.get("is_test_split") == "true" and item_id:
                normalized = normalize_id(item_id)
                if normalized not in held_out:
                    held_out.append(normalized)

    return held_out


def choose_test_users(limit: int) -> list[TestUser]:
    """Loads real users from ChromaDB and selects warm and cold cohorts."""
    users_col, reviews_col = get_collections()
    all_users = users_col.get(limit=394)

    warm_users: list[TestUser] = []
    cold_users: list[TestUser] = []

    for collection_id, metadata in zip(
        all_users.get("ids") or [],
        all_users.get("metadatas") or [],
        strict=False,
    ):
        meta = metadata or {}
        user_id = str(meta.get("user_id") or collection_id).strip()
        platform = str(meta.get("platform") or "yelp").strip() or "yelp"
        review_count = safe_int(meta.get("review_count"), 0)
        held_out_items = get_held_out_items(user_id, reviews_col)

        if not held_out_items:
            continue

        entry = TestUser(
            user_id=user_id,
            platform=platform,
            review_count=review_count,
            held_out_items=held_out_items,
            metadata=meta,
            is_cold_start=review_count < 3,
        )

        if entry.is_cold_start:
            cold_users.append(entry)
        else:
            warm_users.append(entry)

    warm_target = min(15, limit)
    cold_target = max(0, limit - warm_target)

    selected = warm_users[:warm_target] + cold_users[:cold_target]
    if len(selected) < limit:
        overflow = warm_users[warm_target:] + cold_users[cold_target:]
        selected.extend(overflow[: limit - len(selected)])

    return selected[:limit]


def resolve_category(metadata: dict[str, Any]) -> str:
    """Resolves a primary request category from user metadata."""
    top_categories = metadata.get("top_categories", "")
    if isinstance(top_categories, list):
        first = str(top_categories[0]).strip() if top_categories else ""
        return first or "restaurants"

    raw = str(top_categories or "").strip()
    if not raw:
        return "restaurants"
    return raw.split(",")[0].strip() or "restaurants"


def build_payload(user: TestUser, top_k: int = 10) -> dict[str, Any]:
    """Builds the confirmed Task B request payload shape."""
    category = resolve_category(user.metadata)
    return {
        "user_persona": {
            "user_id": user.user_id,
            "platform": user.platform,
            "preferences": {},
            "history": [],
            "persona_text": "",
        },
        "query": "recommend something based on my history",
        "request_context": {
            "category": category,
            "target_domain": "food",
            "item_attributes": {},
            "constraints": [],
        },
        "top_k": top_k,
        "session_id": f"eval_{normalize_id(user.user_id)[:8]}",
        "nigerian_mode": False,
        "enable_cross_domain": False,
    }


def extract_recommended_items(payload: dict[str, Any]) -> tuple[list[str], list[float], list[str], list[str]]:
    """Extracts item IDs and associated metadata from the Task B response body."""
    recommended_ids: list[str] = []
    scores: list[float] = []
    explanations: list[str] = []
    thinking = [str(step) for step in payload.get("thinking", [])]

    for recommendation in payload.get("recommendations", []):
        item = recommendation.get("item") or {}
        item_id = str(item.get("item_id") or recommendation.get("item_id") or "").strip()
        if not item_id:
            continue
        recommended_ids.append(item_id)
        scores.append(safe_float(recommendation.get("score"), 0.0))
        explanations.append(str(recommendation.get("explanation") or ""))

    return recommended_ids, scores, explanations, thinking


def hit_rate_at_k(recommended: list[str], relevant: list[str], k: int = 10) -> float:
    """Computes Hit Rate@K with normalized ID matching."""
    recommended_normalized = {normalize_id(item_id) for item_id in recommended[:k]}
    relevant_normalized = {normalize_id(item_id) for item_id in relevant}
    hits = len(recommended_normalized & relevant_normalized)
    return 1.0 if hits > 0 else 0.0


def ndcg_at_k(recommended: list[str], relevant: list[str], k: int = 10) -> float:
    """Computes NDCG@K with normalized ID matching."""
    relevant_normalized = {normalize_id(item_id) for item_id in relevant}
    if not relevant_normalized:
        return 0.0

    dcg = 0.0
    for index, item_id in enumerate(recommended[:k]):
        if normalize_id(item_id) in relevant_normalized:
            dcg += 1.0 / math.log2(index + 2)

    ideal_hits = min(len(relevant_normalized), k)
    idcg = sum(1.0 / math.log2(index + 2) for index in range(ideal_hits))
    return dcg / idcg if idcg > 0 else 0.0


def evaluate_user(base_url: str, user: TestUser) -> RecommendationResult | None:
    """Calls Task B for one user and computes ranking metrics."""
    response = request_with_retry(
        "post",
        f"{base_url}/recommend",
        json=build_payload(user),
        timeout=DEFAULT_TIMEOUT,
    )

    if not response.ok:
        logger.error(
            "Task B request failed for user %s with status %s: %s",
            user.user_id,
            response.status_code,
            response.text[:500],
        )
        return None

    try:
        payload = response.json()
    except ValueError:
        logger.error("Task B returned non-JSON response for user %s", user.user_id)
        return None

    recommended_items, scores, explanations, thinking = extract_recommended_items(payload)
    ndcg_score = ndcg_at_k(recommended_items, user.held_out_items, k=10)
    hit_rate = hit_rate_at_k(recommended_items, user.held_out_items, k=10)

    return RecommendationResult(
        user_id=user.user_id,
        platform=user.platform,
        review_count=user.review_count,
        held_out_items=user.held_out_items,
        recommended_items=recommended_items,
        scores=scores,
        explanations=explanations,
        thinking=thinking,
        is_cold_start=user.is_cold_start,
        ndcg_at_10=ndcg_score,
        hit_rate_at_10=hit_rate,
    )


def average(values: list[float]) -> float:
    """Returns the mean of a numeric list or 0.0 when empty."""
    return sum(values) / len(values) if values else 0.0


def compute_metrics(results: list[RecommendationResult]) -> EvaluationMetrics:
    """Computes overall, warm, and cold-start metrics."""
    warm_results = [result for result in results if not result.is_cold_start]
    cold_results = [result for result in results if result.is_cold_start]

    return EvaluationMetrics(
        users_evaluated=len(results),
        warm_users=len(warm_results),
        cold_users=len(cold_results),
        overall_ndcg_at_10=average([result.ndcg_at_10 for result in results]),
        overall_hit_rate_at_10=average([result.hit_rate_at_10 for result in results]),
        warm_ndcg_at_10=average([result.ndcg_at_10 for result in warm_results]),
        warm_hit_rate_at_10=average([result.hit_rate_at_10 for result in warm_results]),
        cold_ndcg_at_10=average([result.ndcg_at_10 for result in cold_results]),
        cold_hit_rate_at_10=average([result.hit_rate_at_10 for result in cold_results]),
    )


def print_results_table(metrics: EvaluationMetrics) -> None:
    """Prints the requested Task B summary table."""
    print("\n" + "=" * 40)
    print("TASK B EVALUATION RESULTS")
    print("=" * 40)
    print(
        f"Users evaluated: {metrics.users_evaluated} "
        f"({metrics.warm_users} warm, {metrics.cold_users} cold)"
    )
    print("")
    print("Overall:")
    print(f"  NDCG@10:      {metrics.overall_ndcg_at_10:.4f}")
    print(f"  Hit Rate@10:  {metrics.overall_hit_rate_at_10:.4f}")
    print("")
    print(f"Warm Users (n={metrics.warm_users}):")
    print(f"  NDCG@10:      {metrics.warm_ndcg_at_10:.4f}")
    print(f"  Hit Rate@10:  {metrics.warm_hit_rate_at_10:.4f}")
    print("")
    print(f"Cold-Start Users (n={metrics.cold_users}):")
    print(f"  NDCG@10:      {metrics.cold_ndcg_at_10:.4f}")
    print(f"  Hit Rate@10:  {metrics.cold_hit_rate_at_10:.4f}")


def save_results(results: list[RecommendationResult], metrics: EvaluationMetrics) -> None:
    """Writes JSON results and a text summary for Task B."""
    eval_dir = project_root() / "eval"
    json_path = eval_dir / "eval_results_task_b.json"
    summary_path = eval_dir / "task_b_summary.txt"

    output_data = {
        "evaluation_metrics": asdict(metrics),
        "user_results": [asdict(result) for result in results],
    }
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(output_data, file, indent=2)

    summary_lines = [
        "TASK B EVALUATION RESULTS",
        "=" * 40,
        f"Users evaluated: {metrics.users_evaluated} ({metrics.warm_users} warm, {metrics.cold_users} cold)",
        "",
        "Overall:",
        f"  NDCG@10:      {metrics.overall_ndcg_at_10:.4f}",
        f"  Hit Rate@10:  {metrics.overall_hit_rate_at_10:.4f}",
        "",
        f"Warm Users (n={metrics.warm_users}):",
        f"  NDCG@10:      {metrics.warm_ndcg_at_10:.4f}",
        f"  Hit Rate@10:  {metrics.warm_hit_rate_at_10:.4f}",
        "",
        f"Cold-Start Users (n={metrics.cold_users}):",
        f"  NDCG@10:      {metrics.cold_ndcg_at_10:.4f}",
        f"  Hit Rate@10:  {metrics.cold_hit_rate_at_10:.4f}",
    ]
    with summary_path.open("w", encoding="utf-8") as file:
        file.write("\n".join(summary_lines) + "\n")

    logger.info("Results saved to %s and %s", json_path, summary_path)


def main() -> None:
    """Runs the full Task B evaluation flow."""
    args = parse_args()
    limit = max(1, args.limit)

    check_connection(args.base_url)
    users = choose_test_users(limit)
    if not users:
        logger.error("No real Task B users with held-out test items were loaded from ChromaDB.")
        sys.exit(1)

    logger.info("Loaded %s real Task B users from ChromaDB", len(users))
    results: list[RecommendationResult] = []

    for index, user in enumerate(users, start=1):
        print(f"Evaluating user {index}/{len(users)}...")
        result = evaluate_user(args.base_url, user)
        if result is not None:
            results.append(result)

    if not results:
        logger.error("Task B evaluation produced no successful results.")
        sys.exit(1)

    metrics = compute_metrics(results)
    print_results_table(metrics)
    save_results(results, metrics)


if __name__ == "__main__":
    main()
