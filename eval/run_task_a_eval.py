"""Task A evaluation harness.

Loads test split from data/splits.json, calls Task A service via HTTP,
computes ROUGE-1, ROUGE-L, BERTScore-F1, RMSE, and saves results.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp
import numpy as np
import pandas as pd
from bert_score import score as bert_score
from rouge_score import rouge_scorer
from sklearn.metrics import mean_squared_error
from tqdm import tqdm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TestSample:
    """A single test sample for Task A evaluation."""
    user_id: str
    platform: str
    review_id: str
    item_id: str
    item_name: str
    item_category: str
    reference_review: str
    actual_rating: float


@dataclass
class EvalResult:
    """Evaluation results for a single sample."""
    sample_id: str
    generated_review: str
    predicted_rating: float
    reference_review: str
    actual_rating: float
    rouge1: float
    rougeL: float
    bertscore_f1: float


@dataclass
class AggregateMetrics:
    """Aggregate metrics across all test samples."""
    num_samples: int
    rouge1_mean: float
    rouge1_std: float
    rougeL_mean: float
    rougeL_std: float
    bertscore_f1_mean: float
    bertscore_f1_std: float
    rmse: float
    mae: float


class TaskAEvaluator:
    """Task A evaluation harness."""
    
    def __init__(self, task_a_url: str = "http://localhost:8001"):
        self.task_a_url = task_a_url
        self.session: aiohttp.ClientSession | None = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def call_task_a(self, sample: TestSample) -> tuple[str, float]:
        """Call Task A service to generate review and rating."""
        if not self.session:
            raise RuntimeError("Session not initialized")
            
        payload = {
            "user_id": sample.user_id,
            "platform": sample.platform,
            "item_id": sample.item_id,
            "item_name": sample.item_name,
            "item_category": sample.item_category,
            "nigerian_intensity": "light"  # Use light Nigerian mode for evaluation
        }
        
        try:
            async with self.session.post(
                f"{self.task_a_url}/generate-review",
                json=payload,
                timeout=30
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["review_text"], data["rating"]
                else:
                    logger.error(f"Task A API error: {response.status}")
                    return "", 0.0
        except Exception as e:
            logger.error(f"Error calling Task A: {e}")
            return "", 0.0
            
    async def evaluate_sample(self, sample: TestSample) -> EvalResult | None:
        """Evaluate a single test sample."""
        generated_review, predicted_rating = await self.call_task_a(sample)
        
        if not generated_review:
            return None
            
        # Compute ROUGE scores
        scorer = rouge_scorer.RougeScorer(["rouge1", "rougeL"], use_stemmer=True)
        rouge_scores = scorer.score(generated_review, sample.reference_review)
        
        # Compute BERTScore
        _, _, bert_f1 = bert_score(
            [generated_review],
            [sample.reference_review],
            lang="en",
            verbose=False
        )
        
        return EvalResult(
            sample_id=sample.review_id,
            generated_review=generated_review,
            predicted_rating=predicted_rating,
            reference_review=sample.reference_review,
            actual_rating=sample.actual_rating,
            rouge1=rouge_scores["rouge1"].fmeasure,
            rougeL=rouge_scores["rougeL"].fmeasure,
            bertscore_f1=bert_f1.item()
        )
        
    def compute_aggregate_metrics(self, results: list[EvalResult]) -> AggregateMetrics:
        """Compute aggregate metrics across all results."""
        if not results:
            return AggregateMetrics(
                num_samples=0,
                rouge1_mean=0.0,
                rouge1_std=0.0,
                rougeL_mean=0.0,
                rougeL_std=0.0,
                bertscore_f1_mean=0.0,
                bertscore_f1_std=0.0,
                rmse=0.0,
                mae=0.0
            )
            
        rouge1_scores = [r.rouge1 for r in results]
        rougeL_scores = [r.rougeL for r in results]
        bertscore_scores = [r.bertscore_f1 for r in results]
        predicted_ratings = [r.predicted_rating for r in results]
        actual_ratings = [r.actual_rating for r in results]
        
        rmse = np.sqrt(mean_squared_error(actual_ratings, predicted_ratings))
        mae = np.mean(np.abs(np.array(actual_ratings) - np.array(predicted_ratings)))
        
        return AggregateMetrics(
            num_samples=len(results),
            rouge1_mean=np.mean(rouge1_scores),
            rouge1_std=np.std(rouge1_scores),
            rougeL_mean=np.mean(rougeL_scores),
            rougeL_std=np.std(rougeL_scores),
            bertscore_f1_mean=np.mean(bertscore_scores),
            bertscore_f1_std=np.std(bertscore_scores),
            rmse=rmse,
            mae=mae
        )
        
    def print_results_table(self, metrics: AggregateMetrics, results: list[EvalResult]):
        """Print formatted results table."""
        print("\n" + "="*80)
        print("TASK A EVALUATION RESULTS")
        print("="*80)
        
        print(f"\nSample Count: {metrics.num_samples}")
        
        print("\nText Quality Metrics:")
        print(f"{'Metric':<15} {'Mean':<10} {'Std':<10}")
        print(f"{'-'*15} {'-'*10} {'-'*10}")
        print(f"{'ROUGE-1':<15} {metrics.rouge1_mean:.4f}    {metrics.rouge1_std:.4f}")
        print(f"{'ROUGE-L':<15} {metrics.rougeL_mean:.4f}    {metrics.rougeL_std:.4f}")
        print(f"{'BERTScore-F1':<15} {metrics.bertscore_f1_mean:.4f}    {metrics.bertscore_f1_std:.4f}")
        
        print("\nRating Accuracy Metrics:")
        print(f"{'RMSE':<10} {metrics.rmse:.4f}")
        print(f"{'MAE':<10} {metrics.mae:.4f}")
        
        # Show top 5 samples
        if results:
            print("\nTop 5 Samples (by ROUGE-L):")
            sorted_results = sorted(results, key=lambda x: x.rougeL, reverse=True)[:5]
            for i, result in enumerate(sorted_results, 1):
                print(f"\n{i}. Sample {result.sample_id[:8]}...")
                print(f"   ROUGE-L: {result.rougeL:.4f}, BERTScore: {result.bertscore_f1:.4f}")
                print(f"   Predicted Rating: {result.predicted_rating:.1f}, Actual: {result.actual_rating:.1f}")
                
    async def run_evaluation(self, test_samples: list[TestSample], max_samples: int = 100) -> tuple[AggregateMetrics, list[EvalResult]]:
        """Run evaluation on test samples."""
        if max_samples and len(test_samples) > max_samples:
            logger.info(f"Limiting evaluation to {max_samples} samples")
            test_samples = test_samples[:max_samples]
            
        results = []
        async with self:
            for sample in tqdm(test_samples, desc="Evaluating Task A"):
                result = await self.evaluate_sample(sample)
                if result:
                    results.append(result)
                    
        metrics = self.compute_aggregate_metrics(results)
        return metrics, results


def load_test_samples(splits_path: Path) -> list[TestSample]:
    """Load test samples from splits.json."""
    if not splits_path.exists():
        logger.error(f"splits.json not found at {splits_path}")
        return []
        
    with open(splits_path) as f:
        splits = json.load(f)
        
    # Load reviews from ChromaDB or from processed data
    # For now, we'll create mock test samples
    test_samples = []
    
    # This would normally load from actual data
    # For the hackathon, we'll create synthetic test samples
    logger.warning("Using synthetic test samples - replace with actual data loading")
    
    # Create 20 synthetic test samples
    for i in range(20):
        platform = ["yelp", "amazon", "goodreads"][i % 3]
        test_samples.append(TestSample(
            user_id=f"user_{i}",
            platform=platform,
            review_id=f"review_{i}",
            item_id=f"item_{i}",
            item_name=f"Sample {platform.capitalize()} Item {i}",
            item_category=["restaurant", "electronics", "book"][i % 3],
            reference_review=f"This is a reference review for {platform} item {i}. The quality was good and service was prompt.",
            actual_rating=float(3 + (i % 3))  # Ratings between 3-5
        ))
        
    return test_samples


async def main():
    """Main evaluation function."""
    # Paths
    project_root = Path(__file__).parent.parent
    splits_path = project_root / "data" / "splits.json"
    output_path = project_root / "eval" / "eval_results_task_a.json"
    
    # Load test samples
    test_samples = load_test_samples(splits_path)
    if not test_samples:
        logger.error("No test samples loaded")
        sys.exit(1)
        
    logger.info(f"Loaded {len(test_samples)} test samples")
    
    # Run evaluation
    evaluator = TaskAEvaluator()
    metrics, results = await evaluator.run_evaluation(test_samples, max_samples=50)
    
    # Print results
    evaluator.print_results_table(metrics, results)
    
    # Save results
    output_data = {
        "aggregate_metrics": {
            "num_samples": metrics.num_samples,
            "rouge1_mean": metrics.rouge1_mean,
            "rouge1_std": metrics.rouge1_std,
            "rougeL_mean": metrics.rougeL_mean,
            "rougeL_std": metrics.rougeL_std,
            "bertscore_f1_mean": metrics.bertscore_f1_mean,
            "bertscore_f1_std": metrics.bertscore_f1_std,
            "rmse": metrics.rmse,
            "mae": metrics.mae
        },
        "sample_results": [
            {
                "sample_id": r.sample_id,
                "generated_review": r.generated_review,
                "predicted_rating": r.predicted_rating,
                "reference_review": r.reference_review,
                "actual_rating": r.actual_rating,
                "rouge1": r.rouge1,
                "rougeL": r.rougeL,
                "bertscore_f1": r.bertscore_f1
            }
            for r in results
        ]
    }
    
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)
        
    logger.info(f"Results saved to {output_path}")
    
    # Also save as CSV for easy analysis
    csv_path = project_root / "eval" / "eval_results_task_a.csv"
    df = pd.DataFrame([
        {
            "sample_id": r.sample_id,
            "predicted_rating": r.predicted_rating,
            "actual_rating": r.actual_rating,
            "rouge1": r.rouge1,
            "rougeL": r.rougeL,
            "bertscore_f1": r.bertscore_f1
        }
        for r in results
    ])
    df.to_csv(csv_path, index=False)
    logger.info(f"CSV results saved to {csv_path}")


if __name__ == "__main__":
    asyncio.run(main())