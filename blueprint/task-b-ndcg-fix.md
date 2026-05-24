In eval/run_task_b_eval.py, fix the ndcg_at_k and hit_rate_at_k 
functions to normalize IDs by stripping ALL platform prefixes before 
comparing recommended vs held-out items:

def normalize_id(item_id: str) -> str:
    """Strip platform prefix for comparison."""
    for prefix in ("yelp_", "amazon_", "goodreads_"):
        if item_id.startswith(prefix):
            return item_id[len(prefix):]
    return item_id

# In hit_rate_at_k:
recommended_normalized = {normalize_id(i) for i in recommended[:k]}
relevant_normalized = {normalize_id(i) for i in relevant}
hits = len(recommended_normalized & relevant_normalized)
return 1.0 if hits > 0 else 0.0

# In ndcg_at_k:
relevant_normalized = {normalize_id(i) for i in relevant}
for i, iid in enumerate(recommended[:k]):
    if normalize_id(iid) in relevant_normalized:
        dcg += 1.0 / np.log2(i + 2)

Output only the two changed functions.