"""Runs a lightweight Task B evaluation loop."""

from __future__ import annotations

from sklearn.metrics import ndcg_score


def main() -> None:
    ground_truth = [[3.0, 2.0, 1.0]]
    model_scores = [[0.91, 0.73, 0.22]]
    score = ndcg_score(ground_truth, model_scores)
    print({"ndcg": score})


if __name__ == "__main__":
    main()
