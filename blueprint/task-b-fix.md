<context>
Task B is now querying real ChromaDB data but has 4 remaining bugs.

CONFIRMED FROM LOGS:

BUG 1 — item_id prefix mismatch in history retrieval (Tests 1 & 2)
  Reviews store item_id as raw ID: "L3V21nAe-CicW2bvtNWa0g"
  Items collection stores as: "yelp_L3V21nAe-CicW2bvtNWa0g"
  Lookup fails → title="L3V21nAe-CicW2bvtNWa0g", category="unknown"
  
  Log evidence:
    "[CHROMADB] No items record found for id: L3V21nAe-CicW2bvtNWa0g"

BUG 2 — Negative similarity scores (Tests 3 & 4)
  similarity_score: -0.234, score: -2.34
  ChromaDB returns cosine distances. Current formula: 1 - distance
  When distance > 1, similarity goes negative.
  Correct formula: max(0.0, 1.0 - (distance / 2.0))
  Or simpler: clamp to [0, 1]: max(0.0, min(1.0, 1.0 - distance))

BUG 3 — LLM ranker not generating real explanations
  All explanations follow this template:
  "{name} fits the request because it aligns with {category} 
   and the user's known preferences."
  This means the LLM ranker is not being called or its output
  is being discarded and the template is used as fallback.

BUG 4 — top_categories parsed as ['unknown']
  ChromaDB metadata stores: top_categories="Grocery, Arts & Crafts"
  Agent reads it but produces: ['unknown']
  The field name in metadata is "top_categories" (from to_metadata())
  but agent may be reading "preferred_categories" or similar.

Files to fix:
[PASTE task_b/retriever.py]
[PASTE task_b/ranker.py]
[PASTE task_b/agent.py]
[PASTE shared/vector_store.py]
</context>

<fixes>

FIX 1 — task_b/retriever.py: prefix item_id before lookup

In retrieve_user_history_items(), after getting item_id from 
review metadata, attempt lookup with platform prefix:

  raw_item_id = (m or {}).get("item_id", "")
  platform = (m or {}).get("platform", "")
  
  # Build candidate IDs to try for item lookup
  item_id_candidates = [raw_item_id]
  if platform and not raw_item_id.startswith(f"{platform}_"):
      item_id_candidates.append(f"{platform}_{raw_item_id}")
  # Also try yelp_ prefix as default for Yelp users
  if not raw_item_id.startswith("yelp_"):
      item_id_candidates.append(f"yelp_{raw_item_id}")
  
  # Try each candidate to resolve item name and category
  resolved_item = None
  for candidate_id in item_id_candidates:
      item_record = self.vector_store.get_item_by_id(candidate_id)
      if item_record and item_record.get("metadata"):
          resolved_item = item_record
          break
  
  if resolved_item:
      meta = resolved_item["metadata"]
      result = {
          "item_id": resolved_item["id"],
          "title": meta.get("name", candidate_id),
          "category": meta.get("category", "unknown"),
          "source": "user_history",
          "similarity_score": 0.82,
          "metadata": meta,
      }
  else:
      # Keep raw but log the miss
      logger.warning("[RETRIEVER] Could not resolve item: %s", raw_item_id)
      result = {
          "item_id": raw_item_id,
          "title": raw_item_id,
          "category": "unknown",
          "source": "user_history_unresolved",
          "similarity_score": 0.82,
          "metadata": {"rating": float((m or {}).get("rating", 3.0))},
      }

FIX 2 — shared/vector_store.py OR task_b/retriever.py: 
fix similarity score formula

Wherever distances from ChromaDB are converted to similarity scores,
replace:
  similarity = 1 - distance
With:
  similarity = max(0.0, min(1.0, 1.0 - (distance / 2.0)))

Also update score calculation in ranker/agent:
  score = similarity * 10   # scale to 0-10
  # clamp: score = max(0.0, min(10.0, score))

FIX 3 — task_b/ranker.py: fix LLM reranking

The ranker must call Gemini to generate a real explanation per item.
Current behavior: template string used for every item.

Check why LLM is not being called. Most likely:
  a) ranker._get_llm_client() returns None (same dotenv issue)
  b) The ranked output is parsed incorrectly and falls back to template

Fix the ranker's explain() or rerank() method:
  - Add: from dotenv import load_dotenv; load_dotenv(override=True)
    at top of ranker.py
  - Add log: logger.info("[RANKER] Calling LLM for %d candidates", 
                         len(candidates))
  - Add log: logger.info("[RANKER] LLM explanation sample: %s", 
                         explanation[:100])
  - If LLM call fails, log the error explicitly:
    logger.error("[RANKER] LLM failed: %s", e, exc_info=True)
  - The explanation prompt must instruct Gemini:
    "For each item, write 2-3 sentences explaining WHY this specific
     item matches this specific user's preferences. Reference the 
     item's actual name, category, and the user's known interests.
     Do not use generic phrases like 'aligns with preferences'."

FIX 4 — task_b/agent.py: fix top_categories parsing

When fetching user metadata from ChromaDB, the field is stored as
a comma-separated string in "top_categories" key.

Replace whatever current parsing is with:
  raw_cats = user_metadata.get("top_categories", "") or \
             user_metadata.get("preferred_categories", "") or ""
  top_categories = [c.strip() for c in raw_cats.split(",") 
                    if c.strip() and c.strip().lower() != "unknown"]
  
  if not top_categories:
      # fallback: use platform defaults
      top_categories = ["restaurants"] if platform == "yelp" else \
                       ["Electronics"] if platform == "amazon" else \
                       ["fiction", "to-read"]
  
  logger.info("[AGENT_B] Resolved categories: %s", top_categories)

Update thinking to show real categories:
  f"Plan: top categories from history are {top_categories}."

<constraints>
- similarity_score must always be in range [0.0, 1.0]
- score must always be positive (0.0 to 10.0)
- item title must never equal item_id (resolve from ChromaDB)
- explanation must be LLM-generated, not a template
- load_dotenv(override=True) at top of ranker.py
- Output all changed files in full with path headers
- No truncation
</constraints>

<expected_after_fix>
Test 1 response:
  item_id: "yelp_L3V21nAe-CicW2bvtNWa0g"   ← prefixed
  title: "Joe's Diner"                        ← real name from items collection
  category: "Restaurants"                     ← real category
  similarity_score: 0.73                      ← positive, 0-1
  score: 7.3                                  ← positive, 0-10
  explanation: "Joe's Diner is a strong match because you've previously 
    reviewed similar casual dining spots and tend to rate mid-range 
    restaurants highly. The Restaurants category aligns with your top 
    preference area."                          ← LLM generated
  
thinking:
  "Plan: top categories from history are ['Grocery', 'Arts & Crafts']"
</expected_after_fix>