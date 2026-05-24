python -m eval.run_task_a_eval --limit 10 --skip-bert
((venv) ) admin@Khais-MacBook-Pro bcthack % python -m eval.run_task_a_eval --limit 10 --skip-bert
Connected to Task A at http://localhost:8001
INFO: chromadb.telemetry.product.posthog: Anonymized telemetry enabled. See                     https://docs.trychroma.com/telemetry for more information.
ERROR: chromadb.telemetry.product.posthog: Failed to send telemetry event ClientStartEvent: capture() takes 1 positional argument but 3 were given
ERROR: chromadb.telemetry.product.posthog: Failed to send telemetry event CollectionGetEvent: capture() takes 1 positional argument but 3 were given
ERROR: chromadb.telemetry.product.posthog: Failed to send telemetry event CollectionGetEvent: capture() takes 1 positional argument but 3 were given
INFO: __main__: Loaded 10 real Task A test samples from ChromaDB
Evaluating sample 1/10...
INFO: absl: Using default tokenizer.
Evaluating sample 2/10...
INFO: absl: Using default tokenizer.
Evaluating sample 3/10...
INFO: absl: Using default tokenizer.
Evaluating sample 4/10...
INFO: absl: Using default tokenizer.
Evaluating sample 5/10...
INFO: absl: Using default tokenizer.
Evaluating sample 6/10...
INFO: absl: Using default tokenizer.
Evaluating sample 7/10...
INFO: absl: Using default tokenizer.
Evaluating sample 8/10...
INFO: absl: Using default tokenizer.
Evaluating sample 9/10...
INFO: absl: Using default tokenizer.
Evaluating sample 10/10...
INFO: absl: Using default tokenizer.

========================================
TASK A EVALUATION RESULTS
========================================
Samples evaluated: 10

Text Quality:
  ROUGE-1 Mean:  0.1867
  ROUGE-1 Std:   0.0485
  ROUGE-L Mean:  0.1139
  ROUGE-L Std:   0.0266
  BERTScore-F1:  skipped

Rating Accuracy:
  RMSE:          1.2454
  MAE:           0.8700
INFO: __main__: Results saved to /Users/admin/Developer/bcthack/eval/eval_results_task_a.json and /Users/admin/Developer/bcthack/eval/eval_results_task_a.csv


python -m eval.run_task_a_eval --limit 30
========================================
TASK A EVALUATION RESULTS
========================================
Samples evaluated: 30

Text Quality:
  ROUGE-1 Mean:  0.1860
  ROUGE-1 Std:   0.0504
  ROUGE-L Mean:  0.1170
  ROUGE-L Std:   0.0341
  BERTScore-F1 Mean: 0.8393
  BERTScore-F1 Std:  0.0102

Rating Accuracy:
  RMSE:          1.0518
  MAE:           0.7633
INFO: __main__: Results saved to /Users/admin/Developer/bcthack/eval/eval_results_task_a.json and /Users/admin/Developer/bcthack/eval/eval_results_task_a.csv


python -m eval.run_task_b_eval --limit 15
========================================
TASK B EVALUATION RESULTS
========================================
Users evaluated: 15 (15 warm, 0 cold)

Overall:
  NDCG@10:      0.0000
  Hit Rate@10:  0.0000

Warm Users (n=15):
  NDCG@10:      0.0000
  Hit Rate@10:  0.0000

Cold-Start Users (n=0):
  NDCG@10:      0.0000
  Hit Rate@10:  0.0000
INFO: __main__: Results saved to /Users/admin/Developer/bcthack/eval/eval_results_task_b.json and /Users/admin/Developer/bcthack/eval/task_b_summary.txt