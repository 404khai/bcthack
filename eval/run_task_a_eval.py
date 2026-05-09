"""Runs a lightweight Task A evaluation loop."""

from __future__ import annotations

from task_a.evaluator import TaskAEvaluator


def main() -> None:
    evaluator = TaskAEvaluator()
    result = evaluator.evaluate(
        predictions=["Great texture and balanced flavour."],
        references=["Balanced flavour and very satisfying texture."],
        ratings=[4.5],
        targets=[5.0],
    )
    print({"rouge_l_f1": result.rouge_l_f1, "rmse": result.rmse})


if __name__ == "__main__":
    main()
