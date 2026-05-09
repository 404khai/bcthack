"""Evaluation helpers for Task A."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from rouge_score import rouge_scorer
from sklearn.metrics import mean_squared_error


@dataclass(slots=True)
class TaskAEvaluationResult:
    rouge_l_f1: float
    rmse: float


class TaskAEvaluator:
    def evaluate(
        self,
        predictions: list[str],
        references: list[str],
        ratings: list[float],
        targets: list[float],
    ) -> TaskAEvaluationResult:
        scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
        rouge_scores = [
            scorer.score(reference, prediction)["rougeL"].fmeasure
            for prediction, reference in zip(predictions, references, strict=False)
        ]
        rmse = sqrt(mean_squared_error(targets, ratings)) if ratings and targets else 0.0
        rouge_average = sum(rouge_scores) / len(rouge_scores) if rouge_scores else 0.0
        return TaskAEvaluationResult(rouge_l_f1=rouge_average, rmse=rmse)
