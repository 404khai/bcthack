
"""Runs a lightweight Task A evaluation loop."""

from __future__ import annotations

import asyncio

from task_a.evaluator import EvalSample, TaskAEvaluator


async def main() -> None:
    """Executes a small demonstration batch evaluation for Task A."""
    evaluator = TaskAEvaluator()
    report = await evaluator.run_batch_eval(
        [
            EvalSample(
                generated_review="The flavours felt balanced and the service stayed warm throughout.",
                reference_review="Balanced flavours with warm service made the visit satisfying.",
                predicted_rating=4.4,
                actual_rating=4.8,
            )
        ]
    )
    print(
        {
            "samples": report.sample_count,
            "rouge": report.rouge,
            "bertscore": report.bertscore,
            "rmse": report.rmse,
        }
    )


if __name__ == "__main__":
    asyncio.run(main())
