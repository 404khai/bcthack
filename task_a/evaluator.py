
"""Evaluation helpers for Task A."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from statistics import mean

from bert_score import score as bert_score
from rouge_score import rouge_scorer
from sklearn.metrics import mean_squared_error


@dataclass(slots=True)
class EvalSample:
    """Single evaluation sample for Task A batch scoring."""

    generated_review: str
    reference_review: str
    predicted_rating: float
    actual_rating: float


@dataclass(slots=True)
class EvalReport:
    """Aggregated evaluation metrics for a Task A batch."""

    sample_count: int
    rouge: dict[str, float]
    bertscore: dict[str, float]
    rmse: float
    metadata: dict[str, float] = field(default_factory=dict)


def compute_rouge(generated: str, reference: str) -> dict[str, float]:
    """Computes ROUGE-L precision, recall, and F1 for one sample."""
    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
    score = scorer.score(reference, generated)["rougeL"]
    return {
        "precision": round(score.precision, 4),
        "recall": round(score.recall, 4),
        "f1": round(score.fmeasure, 4),
    }


def compute_bertscore(generated: str, reference: str) -> dict[str, float]:
    """Computes BERTScore precision, recall, and F1 for one sample."""
    precision, recall, f1 = bert_score(
        [generated],
        [reference],
        lang="en",
        verbose=False,
        rescale_with_baseline=True,
    )
    return {
        "precision": round(float(precision.mean().item()), 4),
        "recall": round(float(recall.mean().item()), 4),
        "f1": round(float(f1.mean().item()), 4),
    }


def compute_rmse(predicted_ratings: list[float], actual_ratings: list[float]) -> float:
    """Computes RMSE between predicted and actual ratings."""
    if not predicted_ratings or not actual_ratings:
        return 0.0
    return round(sqrt(mean_squared_error(actual_ratings, predicted_ratings)), 4)


class TaskAEvaluator:
    """Runs Task A evaluation metrics over generated review batches."""

    def compute_rouge(self, generated: str, reference: str) -> dict[str, float]:
        """Delegates single-sample ROUGE computation."""
        return compute_rouge(generated, reference)

    def compute_bertscore(self, generated: str, reference: str) -> dict[str, float]:
        """Delegates single-sample BERTScore computation."""
        return compute_bertscore(generated, reference)

    def compute_rmse(self, predicted_ratings: list[float], actual_ratings: list[float]) -> float:
        """Delegates RMSE computation."""
        return compute_rmse(predicted_ratings, actual_ratings)

    async def run_batch_eval(self, test_samples: list[EvalSample]) -> EvalReport:
        """Aggregates ROUGE, BERTScore, and RMSE over a list of evaluation samples."""
        if not test_samples:
            return EvalReport(
                sample_count=0,
                rouge={"precision": 0.0, "recall": 0.0, "f1": 0.0},
                bertscore={"precision": 0.0, "recall": 0.0, "f1": 0.0},
                rmse=0.0,
            )

        rouge_scores = [
            compute_rouge(sample.generated_review, sample.reference_review)
            for sample in test_samples
        ]
        bert_scores = [
            compute_bertscore(sample.generated_review, sample.reference_review)
            for sample in test_samples
        ]
        rmse = compute_rmse(
            [sample.predicted_rating for sample in test_samples],
            [sample.actual_rating for sample in test_samples],
        )

        return EvalReport(
            sample_count=len(test_samples),
            rouge={
                "precision": round(mean(score["precision"] for score in rouge_scores), 4),
                "recall": round(mean(score["recall"] for score in rouge_scores), 4),
                "f1": round(mean(score["f1"] for score in rouge_scores), 4),
            },
            bertscore={
                "precision": round(mean(score["precision"] for score in bert_scores), 4),
                "recall": round(mean(score["recall"] for score in bert_scores), 4),
                "f1": round(mean(score["f1"] for score in bert_scores), 4),
            },
            rmse=rmse,
            metadata={"sample_count": float(len(test_samples))},
        )
