<context>
Both eval scripts send wrong payload formats causing 422 errors.
Both use synthetic data instead of real ChromaDB data.

CONFIRMED CORRECT PAYLOAD FORMATS:

Task A — POST http://localhost:8001/generate-review:
{
  "user_persona": {
    "user_id": "yelp__BcWyKQL16ndpBdggh2kNA",
    "platform": "yelp",
    "review_history": [],
    "preferences": {}
  },
  "item_details": {
    "item_id": "yelp_8c0r7olQSYGcws0bTd3ikw",
    "name": "Zesty Tsunami",
    "category": "Hawaiian",
    "attributes": {}
  },
  "nigerian_mode": false,
  "nigerian_intensity": "medium"
}

Task B — POST http://localhost:8002/recommend:
{
  "user_persona": {
    "user_id": "yelp__BcWyKQL16ndpBdggh2kNA",
    "platform": "yelp",
    "preferences": {},
    "history": [],
    "persona_text": ""
  },
  "query": "recommend something based on my history",
  "request_context": {
    "category": "restaurants",
    "target_domain": "food",
    "item_attributes": {},
    "constraints": []
  },
  "top_k": 10,
  "session_id": "eval_session_001",
  "nigerian_mode": false,
  "enable_cross_domain": false
}

ChromaDB is at path from env var CHROMA_PERSIST_DIR=./chroma_data
Collections: users(394), items(499), reviews(5212)

Review metadata fields:
  user_id (string), item_id (string), rating (string "3.5" or float),
  platform (string), is_test_split (string "true" or "false")

User metadata fields:
  user_id, platform, review_count, avg_rating, top_categories,
  avg_review_length, vocabulary_size

Item metadata fields:
  name, category, platform, avg_rating

Current broken eval files:
[PASTE eval/run_task_a_eval.py]
[PASTE eval/run_task_b_eval.py]
</context>

<task>
Rewrite BOTH eval files completely.

═══════════════════════════════════════
FILE 1: eval/run_task_a_eval.py
═══════════════════════════════════════

STEP 1 — Load real test samples from ChromaDB:

  from dotenv import load_dotenv
  load_dotenv(override=True)
  import chromadb, os
  
  chroma_path = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
  client = chromadb.PersistentClient(path=chroma_path)
  reviews_col = client.get_collection("reviews")
  items_col = client.get_collection("items")
  
  # Get test reviews
  all_reviews = reviews_col.get(limit=1000)
  test_indices = [
      i for i, meta in enumerate(all_reviews["metadatas"])
      if (meta or {}).get("is_test_split") == "true"
  ]
  
  # Limit to 30 samples max (rate limit awareness)
  test_indices = test_indices[:30]

STEP 2 — For each test review, resolve item name:

  def get_item_name(item_id: str) -> tuple[str, str]:
      """Returns (name, category) for an item_id."""
      # Try direct lookup
      for candidate in [item_id, f"yelp_{item_id}", 
                        f"amazon_{item_id}", f"goodreads_{item_id}"]:
          try:
              result = items_col.get(ids=[candidate])
              if result["ids"]:
                  meta = result["metadatas"][0] or {}
                  return meta.get("name", candidate), meta.get("category", "General")
          except Exception:
              continue
      return item_id, "General"

STEP 3 — Build correct payload per task A schema:

  payload = {
      "user_persona": {
          "user_id": meta["user_id"],
          "platform": meta.get("platform", "yelp"),
          "review_history": [],
          "preferences": {}
      },
      "item_details": {
          "item_id": meta["item_id"],
          "name": item_name,
          "category": item_category,
          "attributes": {}
      },
      "nigerian_mode": False,
      "nigerian_intensity": "medium"
  }

STEP 4 — Call endpoint with timeout=60 (LLM is slow):
  response = requests.post(
      "http://localhost:8001/generate-review",
      json=payload,
      timeout=60
  )
  generated_review = response.json()["review_text"]
  predicted_rating = float(response.json()["rating"])
  actual_rating = float(meta.get("rating", 3.0))
  actual_review = document_text

STEP 5 — Compute metrics per sample:
  ROUGE-1, ROUGE-L via rouge_score
  BERTScore-F1 via bert_score (batch all at end for speed)
  RMSE, MAE via sklearn

STEP 6 — Add CLI args:
  --limit N     (default 30, max samples to evaluate)
  --base-url    (default http://localhost:8001)
  --skip-bert   (skip BERTScore — slow, requires model download)

STEP 7 — Add connection check at startup:
  try:
      r = requests.get(f"{base_url}/health", timeout=5)
      r.raise_for_status()
      print(f"Connected to Task A at {base_url}")
  except Exception:
      print(f"ERROR: Cannot connect to Task A at {base_url}")
      print("Start it with: uvicorn task_a.main:app --port 8001")
      print("Or if using Docker: docker-compose up task_a")
      sys.exit(1)

Use synchronous requests (not aiohttp) — simpler and avoids 
async complexity for a one-off eval script.

═══════════════════════════════════════
FILE 2: eval/run_task_b_eval.py
═══════════════════════════════════════

STEP 1 — Load real test users from ChromaDB:

  users_col = client.get_collection("users")
  all_users = users_col.get(limit=394)
  
  # Split into warm (review_count >= 3) and cold (review_count < 3)
  warm_users = []
  cold_users = []
  for uid, meta in zip(all_users["ids"], all_users["metadatas"]):
      count = int((meta or {}).get("review_count", 0))
      platform = (meta or {}).get("platform", "yelp")
      entry = {"user_id": uid, "platform": platform, 
               "review_count": count, "metadata": meta}
      if count >= 3:
          warm_users.append(entry)
      else:
          cold_users.append(entry)
  
  # Select test users: 15 warm + 5 cold = 20 total
  # (rate limit: 20 users × 1 call = 20 requests)
  test_users = warm_users[:15] + cold_users[:5]

STEP 2 — Get held-out items per user (ground truth):

  def get_held_out_items(user_id: str) -> list[str]:
      """Returns list of item_ids the user actually reviewed (test split)."""
      candidates = [user_id]
      # strip platform prefix to get raw id for review lookup
      for platform in ("yelp_", "amazon_", "goodreads_"):
          if user_id.startswith(platform):
              candidates.append(user_id[len(platform):])
      
      for candidate in candidates:
          try:
              results = reviews_col.get(
                  where={"user_id": candidate},
                  limit=50
              )
              held_out = [
                  meta.get("item_id", "")
                  for meta in (results["metadatas"] or [])
                  if (meta or {}).get("is_test_split") == "true"
                  and meta.get("item_id")
              ]
              if held_out:
                  return held_out
          except Exception:
              continue
      return []

STEP 3 — Build correct payload per task B schema:

  def build_payload(user: dict, query: str, top_k: int = 10) -> dict:
      meta = user["metadata"] or {}
      top_cats = meta.get("top_categories", "")
      category = top_cats.split(",")[0].strip() if top_cats else "restaurants"
      
      return {
          "user_persona": {
              "user_id": user["user_id"],
              "platform": user["platform"],
              "preferences": {},
              "history": [],
              "persona_text": ""
          },
          "query": query,
          "request_context": {
              "category": category,
              "target_domain": "food",
              "item_attributes": {},
              "constraints": []
          },
          "top_k": top_k,
          "session_id": f"eval_{user['user_id'][:8]}",
          "nigerian_mode": False,
          "enable_cross_domain": False
      }

STEP 4 — Call endpoint and extract recommended item_ids:

  response = requests.post(
      "http://localhost:8002/recommend",
      json=payload,
      timeout=60
  )
  recs = response.json().get("recommendations", [])
  recommended_ids = [
      r["item"]["item_id"] for r in recs
      if r.get("item", {}).get("item_id")
  ]

STEP 5 — Compute NDCG@10 and Hit Rate@10:

  def hit_rate_at_k(recommended: list[str], 
                    relevant: list[str], k: int = 10) -> float:
      top_k = set(recommended[:k])
      # Also check without platform prefix
      top_k_stripped = set()
      for iid in top_k:
          top_k_stripped.add(iid)
          for p in ("yelp_","amazon_","goodreads_"):
              if iid.startswith(p):
                  top_k_stripped.add(iid[len(p):])
      relevant_set = set(relevant)
      hits = len(relevant_set & top_k_stripped)
      return 1.0 if hits > 0 else 0.0

  def ndcg_at_k(recommended: list[str], 
                relevant: list[str], k: int = 10) -> float:
      relevant_set = set(relevant)
      # strip prefixes for matching
      def normalize(iid):
          for p in ("yelp_","amazon_","goodreads_"):
              if iid.startswith(p):
                  return iid[len(p):]
          return iid
      
      dcg = 0.0
      for i, iid in enumerate(recommended[:k]):
          if normalize(iid) in relevant_set or iid in relevant_set:
              dcg += 1.0 / np.log2(i + 2)
      
      ideal_hits = min(len(relevant_set), k)
      idcg = sum(1.0 / np.log2(i + 2) for i in range(ideal_hits))
      return dcg / idcg if idcg > 0 else 0.0

STEP 6 — Track cold-start separately:
  For cold users (review_count < 3), track separately:
  cold_hit_rates, cold_ndcg scores
  Report alongside warm user metrics

STEP 7 — Add CLI args:
  --limit N     (default 20)
  --base-url    (default http://localhost:8002)

STEP 8 — Connection check same as Task A.

STEP 9 — Results table format:

  ════════════════════════════════════════
  TASK B EVALUATION RESULTS
  ════════════════════════════════════════
  Users evaluated: 20 (15 warm, 5 cold)
  
  Overall:
    NDCG@10:      X.XXXX
    Hit Rate@10:  X.XXXX
  
  Warm Users (n=15):
    NDCG@10:      X.XXXX
    Hit Rate@10:  X.XXXX
  
  Cold-Start Users (n=5):
    NDCG@10:      X.XXXX  
    Hit Rate@10:  X.XXXX

Save to eval_results_task_b.json and task_b_summary.txt

<constraints>
- load_dotenv(override=True) at very top of both files
- Use synchronous requests not aiohttp
- timeout=60 on all API calls (LLM is slow)
- Gracefully handle 429 rate limit errors:
    if response.status_code == 429:
        logger.warning("Rate limit hit, waiting 35s...")
        time.sleep(35)
        # retry once
- Print progress: "Evaluating user X/20..."
- Both files must have __main__ guard
- Output both files in full with path headers
- No truncation
</constraints>