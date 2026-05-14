<role>
Senior Python Engineer writing a test data generator for a FastAPI service.
</role>

<context>
We have a running ChromaDB instance at ./chroma_db with three collections:
- users: 394 documents with metadata {platform, avg_rating, review_count}
- items: 499 documents with metadata {platform, category, name}
- reviews: 5212 documents with metadata {user_id, item_id, rating, platform}

We need to generate a realistic test payload for Task A's POST /generate-review
endpoint and Task B's POST /recommend endpoint using REAL data from ChromaDB.

Task A request schema:
{
  "user_persona": {
    "user_id": str,
    "platform": str,
    "review_history": [
      {
        "item_id": str,
        "text": str,
        "rating": float,
        "category": str,
        "created_at": str,
        "attributes": {}
      }
    ],
    "preferences": {}
  },
  "item_details": {
    "item_id": str,
    "name": str,
    "category": str,
    "attributes": {}
  },
  "nigerian_mode": bool,
  "nigerian_intensity": "light" | "medium" | "full"
}

Task B request schema:
{
  "user_id": str,
  "platform": str,
  "category": str,
  "top_k": int,
  "nigerian_mode": bool,
  "session_id": str
}
</context>

<task>
Create a single script: data/generate_test_payloads.py

The script must:

1. Connect to ChromaDB at CHROMA_PERSIST_DIR (env var, default ./chroma_db)

2. Pick 3 real test users — one from each platform:
   - One yelp user
   - One amazon user  
   - One goodreads user
   Use collection.get() with a where filter on platform metadata

3. For each user, fetch their actual reviews from the reviews collection:
   Use collection.query() or collection.get() filtering by user_id metadata
   Take up to 5 reviews per user

4. For each user, fetch a real item they have NOT reviewed:
   Pick any item from the items collection on the same platform

5. Build complete valid payloads for both Task A and Task B
   using the real user_ids, item_ids, review texts and ratings

6. Save outputs to:
   - data/test_payloads/task_a_yelp.json
   - data/test_payloads/task_a_amazon.json
   - data/test_payloads/task_a_goodreads.json
   - data/test_payloads/task_b_yelp.json
   - data/test_payloads/task_b_amazon.json
   - data/test_payloads/task_b_goodreads.json

7. Also print a ready-to-use curl command for each payload, like:
   curl -X POST "http://localhost:8001/generate-review" \
     -H "Content-Type: application/json" \
     -d @data/test_payloads/task_a_yelp.json

8. Also generate one COLD START payload for Task B:
   - user_id: "cold_user_lagos_001"
   - platform: "yelp"
   - review_history: []
   - Save as data/test_payloads/task_b_cold_start.json

<constraints>
- Use chromadb.PersistentClient, not the HTTP client
- All file paths via os.makedirs("data/test_payloads", exist_ok=True)
- Pretty-print JSON with indent=2
- Print a summary table at the end showing all generated files
  and the user_id used in each
- If a platform has no users in ChromaDB, print a warning and skip it
</constraints>

Output the complete script with path header and full docstrings.