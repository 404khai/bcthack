"""Task B evaluation harness.

Loads test users from splits.json, calls Task B service, gets top-10 recommendations,
computes NDCG@10 and Hit Rate vs held-out items, tests cold-start users.
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
from sklearn.metrics import ndcg_score
from tqdm import tqdm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TestUser:
    """A test user for Task B evaluation."""
    user_id: str
    platform: str
    review_count: int
    held_out_items: list[str]  # Item IDs held out for testing
    is_cold_start: bool = False
    preferences: dict[str, Any] | None = None


@dataclass
class RecommendationResult:
    """Recommendation results for a single user."""
    user_id: str
    recommended_items: list[str]  # Item IDs in ranked order
    scores: list[float]
    explanations: list[str]
    thinking: str
    is_cold_start: bool


@dataclass
class EvaluationMetrics:
    """Evaluation metrics for Task B."""
    num_users: int
    num_cold_start: int
    ndcg_at_10: float
    hit_rate_at_10: float
    ndcg_cold_start: float
    hit_rate_cold_start: float
    avg_recommendations_per_user: float
    avg_score: float


class TaskBEvaluator:
    """Task B evaluation harness."""
    
    def __init__(self, task_b_url: str = "http://localhost:8002"):
        self.task_b_url = task_b_url
        self.session: aiohttp.ClientSession | None = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def call_task_b(self, user: TestUser, category: str = "all") -> RecommendationResult | None:
        """Call Task B service to get recommendations."""
        if not self.session:
            raise RuntimeError("Session not initialized")
            
        payload = {
            "user_id": user.user_id,
            "platform": user.platform,
            "category": category,
            "top_k": 10,
            "nigerian_mode": False,  # Disable for evaluation consistency
            "session_id": f"eval_{user.user_id}"
        }
        
        if user.preferences:
            payload["preferences"] = user.preferences
            
        try:
            async with self.session.post(
                f"{self.task_b_url}/recommend",
                json=payload,
                timeout=30
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Extract item IDs from recommendations
                    recommended_items = []
                    scores = []
                    explanations = []
                    
                    for rec in data.get("recommendations", []):
                        if "item_id" in rec:
                            recommended_items.append(rec["item_id"])
                            scores.append(rec.get("score", 0.0))
                            explanations.append(rec.get("explanation", ""))
                            
                    return RecommendationResult(
                        user_id=user.user_id,
                        recommended_items=recommended_items,
                        scores=scores,
                        explanations=explanations,
                        thinking=data.get("thinking", ""),
                        is_cold_start=user.is_cold_start
                    )
                else:
                    logger.error(f"Task B API error: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error calling Task B: {e}")
            return None
            
    def compute_ndcg(self, user: TestUser, result: RecommendationResult) -> float:
        """Compute NDCG@10 for a single user."""
        if not result.recommended_items or not user.held_out_items:
            return 0.0
            
        # Create relevance scores: 1 if item is in held_out_items, 0 otherwise
        relevance_scores = []
        for item_id in result.recommended_items[:10]:  # Consider top 10
            relevance = 1.0 if item_id in user.held_out_items else 0.0
            relevance_scores.append(relevance)
            
        # Pad to length 10 if needed
        while len(relevance_scores) < 10:
            relevance_scores.append(0.0)
            
        # Ideal DCG: all held-out items ranked first
        ideal_relevance = [1.0] * min(len(user.held_out_items), 10)
        while len(ideal_relevance) < 10:
            ideal_relevance.append(0.0)
            
        # Compute NDCG
        try:
            # Use sklearn's ndcg_score which expects 2D arrays
            ndcg = ndcg_score(
                [ideal_relevance],
                [relevance_scores],
                k=10
            )
            return ndcg
        except:
            return 0.0
            
    def compute_hit_rate(self, user: TestUser, result: RecommendationResult) -> float:
        """Compute Hit Rate@10 for a single user."""
        if not result.recommended_items or not user.held_out_items:
            return 0.0
            
        # Check if any held-out item is in top 10 recommendations
        hits = 0
        for item_id in result.recommended_items[:10]:
            if item_id in user.held_out_items:
                hits += 1
                
        # Hit rate: 1 if at least one hit, 0 otherwise
        return 1.0 if hits > 0 else 0.0
        
    def compute_metrics(self, users: list[TestUser], results: list[RecommendationResult]) -> EvaluationMetrics:
        """Compute aggregate evaluation metrics."""
        if not results:
            return EvaluationMetrics(
                num_users=0,
                num_cold_start=0,
                ndcg_at_10=0.0,
                hit_rate_at_10=0.0,
                ndcg_cold_start=0.0,
                hit_rate_cold_start=0.0,
                avg_recommendations_per_user=0.0,
                avg_score=0.0
            )
            
        # Map results to users
        result_map = {r.user_id: r for r in results}
        
        # Compute metrics per user
        ndcg_scores = []
        hit_rates = []
        ndcg_cold_scores = []
        hit_rate_cold_scores = []
        total_recommendations = 0
        total_score = 0.0
        
        cold_start_count = 0
        
        for user in users:
            result = result_map.get(user.user_id)
            if not result:
                continue
                
            ndcg = self.compute_ndcg(user, result)
            hit_rate = self.compute_hit_rate(user, result)
            
            ndcg_scores.append(ndcg)
            hit_rates.append(hit_rate)
            total_recommendations += len(result.recommended_items)
            total_score += sum(result.scores) if result.scores else 0.0
            
            if user.is_cold_start:
                cold_start_count += 1
                ndcg_cold_scores.append(ndcg)
                hit_rate_cold_scores.append(hit_rate)
                
        # Compute aggregates
        avg_ndcg = np.mean(ndcg_scores) if ndcg_scores else 0.0
        avg_hit_rate = np.mean(hit_rates) if hit_rates else 0.0
        avg_ndcg_cold = np.mean(ndcg_cold_scores) if ndcg_cold_scores else 0.0
        avg_hit_rate_cold = np.mean(hit_rate_cold_scores) if hit_rate_cold_scores else 0.0
        avg_recommendations = total_recommendations / len(results) if results else 0.0
        avg_score = total_score / total_recommendations if total_recommendations > 0 else 0.0
        
        return EvaluationMetrics(
            num_users=len(results),
            num_cold_start=cold_start_count,
            ndcg_at_10=avg_ndcg,
            hit_rate_at_10=avg_hit_rate,
            ndcg_cold_start=avg_ndcg_cold,
            hit_rate_cold_start=avg_hit_rate_cold,
            avg_recommendations_per_user=avg_recommendations,
            avg_score=avg_score
        )
        
    def print_results_table(self, metrics: EvaluationMetrics):
        """Print formatted results table."""
        print("\n" + "="*80)
        print("TASK B EVALUATION RESULTS")
        print("="*80)
        
        print(f"\nUser Statistics:")
        print(f"{'Total Users':<25} {metrics.num_users}")
        print(f"{'Cold Start Users':<25} {metrics.num_cold_start}")
        print(f"{'Avg Recommendations/User':<25} {metrics.avg_recommendations_per_user:.2f}")
        print(f"{'Avg Recommendation Score':<25} {metrics.avg_score:.4f}")
        
        print("\nOverall Performance:")
        print(f"{'Metric':<20} {'Score':<10}")
        print(f"{'-'*20} {'-'*10}")
        print(f"{'NDCG@10':<20} {metrics.ndcg_at_10:.4f}")
        print(f"{'Hit Rate@10':<20} {metrics.hit_rate_at_10:.4f}")
        
        if metrics.num_cold_start > 0:
            print("\nCold Start Performance:")
            print(f"{'Metric':<20} {'Score':<10}")
            print(f"{'-'*20} {'-'*10}")
            print(f"{'NDCG@10 (Cold)':<20} {metrics.ndcg_cold_start:.4f}")
            print(f"{'Hit Rate@10 (Cold)':<20} {metrics.hit_rate_cold_start:.4f}")
            
        # Interpretation
        print("\nInterpretation:")
        if metrics.ndcg_at_10 >= 0.7:
            print("✓ Excellent ranking quality")
        elif metrics.ndcg_at_10 >= 0.5:
            print("✓ Good ranking quality")
        elif metrics.ndcg_at_10 >= 0.3:
            print("○ Moderate ranking quality")
        else:
            print("○ Needs improvement")
            
        if metrics.hit_rate_at_10 >= 0.8:
            print("✓ Excellent coverage of held-out items")
        elif metrics.hit_rate_at_10 >= 0.6:
            print("✓ Good coverage")
        elif metrics.hit_rate_at_10 >= 0.4:
            print("○ Moderate coverage")
        else:
            print("○ Needs improvement")
            
    async def run_evaluation(self, test_users: list[TestUser], max_users: int = 50) -> tuple[EvaluationMetrics, list[RecommendationResult]]:
        """Run evaluation on test users."""
        if max_users and len(test_users) > max_users:
            logger.info(f"Limiting evaluation to {max_users} users")
            test_users = test_users[:max_users]
            
        results = []
        async with self:
            for user in tqdm(test_users, desc="Evaluating Task B"):
                result = await self.call_task_b(user)
                if result:
                    results.append(result)
                    
        metrics = self.compute_metrics(test_users, results)
        return metrics, results


def load_test_users(splits_path: Path) -> list[TestUser]:
    """Load test users from splits.json."""
    if not splits_path.exists():
        logger.error(f"splits.json not found at {splits_path}")
        return []
        
    with open(splits_path) as f:
        splits = json.load(f)
        
    # Load users from ChromaDB or from processed data
    # For now, we'll create mock test users
    test_users = []
    
    # This would normally load from actual data
    # For the hackathon, we'll create synthetic test users
    logger.warning("Using synthetic test users - replace with actual data loading")
    
    # Create 30 synthetic test users
    for i in range(30):
        platform = ["yelp", "amazon", "goodreads"][i % 3]
        review_count = i % 20 + 1  # 1-20 reviews
        
        # Mark users with <3 reviews as cold-start
        is_cold_start = review_count < 3
        
        # Create 3 held-out items per user
        held_out_items = [f"held_out_{platform}_{i}_{j}" for j in range(3)]
        
        # Add some preferences
        preferences = {
            "likes": ["fast service", "good value"] if platform == "yelp" else 
                     ["durable", "easy to use"] if platform == "amazon" else
                     ["character development", "plot twists"],
            "dislikes": ["long waits", "poor hygiene"] if platform == "yelp" else
                        ["complicated setup", "short battery"] if platform == "amazon" else
                        ["predictable endings", "flat characters"]
        }
        
        test_users.append(TestUser(
            user_id=f"test_user_{i}",
            platform=platform,
            review_count=review_count,
            held_out_items=held_out_items,
            is_cold_start=is_cold_start,
            preferences=preferences
        ))
        
    return test_users


async def main():
    """Main evaluation function."""
    # Paths
    project_root = Path(__file__).parent.parent
    splits_path = project_root / "data" / "splits.json"
    output_path = project_root / "eval" / "eval_results_task_b.json"
    
    # Load test users
    test_users = load_test_users(splits_path)
    if not test_users:
        logger.error("No test users loaded")
        sys.exit(1)
        
    logger.info(f"Loaded {len(test_users)} test users")
    logger.info(f"Cold-start users: {sum(1 for u in test_users if u.is_cold_start)}")
    
    # Run evaluation
    evaluator = TaskBEvaluator()
    metrics, results = await evaluator.run_evaluation(test_users, max_users=30)
    
    # Print results
    evaluator.print_results_table(metrics)
    
    # Save results
    output_data = {
        "evaluation_metrics": {
            "num_users": metrics.num_users,
            "num_cold_start": metrics.num_cold_start,
            "ndcg_at_10": metrics.ndcg_at_10,
            "hit_rate_at_10": metrics.hit_rate_at_10,
            "ndcg_cold_start": metrics.ndcg_cold_start,
            "hit_rate_cold_start": metrics.hit_rate_cold_start,
            "avg_recommendations_per_user": metrics.avg_recommendations_per_user,
            "avg_score": metrics.avg_score
        },
        "user_results": [
            {
                "user_id": r.user_id,
                "recommended_items": r.recommended_items,
                "scores": r.scores,
                "explanations": r.explanations,
                "thinking": r.thinking,
                "is_cold_start": r.is_cold_start
            }
            for r in results
        ]
    }
    
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)
        
    logger.info(f"Results saved to {output_path}")
    
    # Also save as CSV for easy analysis
    csv_path = project_root / "eval" / "eval_results_task_b.csv"
    
    # Flatten results for CSV
    rows = []
    for result in results:
        for idx, (item_id, score, explanation) in enumerate(zip(
            result.recommended_items,
            result.scores,
            result.explanations
        )):
            rows.append({
                "user_id": result.user_id,
                "rank": idx + 1,
                "item_id": item_id,
                "score": score,
                "explanation": explanation,
                "is_cold_start": result.is_cold_start
            })
            
    if rows:
        df = pd.DataFrame(rows)
        df.to_csv(csv_path, index=False)
        logger.info(f"CSV results saved to {csv_path}")
        
    # Save summary statistics
    summary_path = project_root / "eval" / "task_b_summary.txt"
    with open(summary_path, "w") as f:
        f.write("TASK B EVALUATION SUMMARY\n")
        f.write("="*40 + "\n\n")
        f.write(f"Total Users Evaluated: {metrics.num_users}\n")
        f.write(f"Cold Start Users: {metrics.num_cold_start}\n")
        f.write(f"NDCG@10: {metrics.ndcg_at_10:.4f}\n")
        f.write(f"Hit Rate@10: {metrics.hit_rate_at_10:.4f}\n")
        f.write(f"NDCG@10 (Cold Start): {metrics.ndcg_cold_start:.4f}\n")
        f.write(f"Hit Rate@10 (Cold Start): {metrics.hit_rate_cold_start:.4f}\n")
        f.write(f"Avg Recommendations per User: {metrics.avg_recommendations_per_user:.2f}\n")
        f.write(f"Avg Recommendation Score: {metrics.avg_score:.4f}\n")
        
    logger.info(f"Summary saved to {summary_path}")


if __name__ == "__main__":
    asyncio.run(main())