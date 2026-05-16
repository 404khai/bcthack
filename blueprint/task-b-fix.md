<context>
Task B /recommend endpoint returns fake placeholder items for every 
request, including users with 65 reviews in ChromaDB. The agent 
never retrieves real items from ChromaDB.

Evidence:
- User "yelp__BcWyKQL16ndpBdggh2kNA" has 65 reviews but response says 
  "user history contains 0 prior interactions"
- item_ids returned: "explicit-1", "popular-local", "city-favorite" 
  — these are hardcoded placeholders, not real ChromaDB items
- All 4 tests return identical structure regardless of user or query
- strategy is always "cold_start_hybrid" even for warm users
- enable_cross_domain=true is completely ignored in Tests 3 and 4

The same root cause as Task A:
1. CHROMA_PERSIST_DIR not loaded from .env at startup
2. Retriever is generating fake candidates instead of querying ChromaDB
3. Warm user detection is not working

Files to fix:
[PASTE task_b/main.py]
[PASTE task_b/agent.py]
[PASTE task_b/retriever.py]
[PASTE task_b/cold_start.py]
</context>

<fixes>

FIX 1 — task_b/main.py: load dotenv first
First two lines before all other imports:
  from dotenv import load_dotenv
  load_dotenv(override=True)

Add startup log:
  import os
  logger.info("CHROMA_PERSIST_DIR: %s", os.getenv("CHROMA_PERSIST_DIR"))
  logger.info("GEMINI_API_KEY loaded: %s", 
              "yes" if os.getenv("GEMINI_API_KEY") else "NO - MISSING")

FIX 2 — task_b/agent.py: fix warm vs cold user detection

Currently the agent treats every user as cold start because it checks
request.user_persona.history (which is always [] in the request payload)
instead of checking ChromaDB for stored reviews.

Fix the warm/cold detection:
  
  async def _is_warm_user(self, user_id: str) -> bool:
      """Returns True if user has stored reviews in ChromaDB."""
      try:
          results = self.vector_store.get_user_by_id(user_id)
          if results and results.get("metadata"):
              review_count = int(
                  results["metadata"].get("review_count", 0)
              )
              logger.info("[AGENT_B] User %s has %d reviews in ChromaDB",
                          user_id, review_count)
              return review_count >= 3
      except Exception as e:
          logger.warning("[AGENT_B] Could not check user warmth: %s", e)
      return False

Call this at the start of the recommend() method:
  is_warm = await self._is_warm_user(request.user_persona.user_id)
  logger.info("[AGENT_B] User warm: %s", is_warm)

Update thinking log to reflect actual result:
  f"Think: user has {review_count} stored interactions, "
  f"treated as {'warm' if is_warm else 'cold start'}."

FIX 3 — task_b/retriever.py: query real ChromaDB items

The retriever must query the "items" collection in ChromaDB.
Currently it generates fake items. Replace with real queries:

  async def retrieve_candidates(
      self,
      user_id: str,
      category: str,
      query_text: str,
      top_k: int = 20,
      platform: str | None = None,
  ) -> list[dict]:
      """Retrieves real item candidates from ChromaDB."""
      
      logger.info("[RETRIEVER] Querying items for category=%s query=%s",
                  category, query_text[:50])
      
      # Build where filter — try with category first, fallback without
      candidates = []
      
      # Attempt 1: filter by category
      try:
          where = {"category": {"$eq": category}} if category else None
          results = self.vector_store.query(
              collection_name="items",
              query_texts=[query_text],
              n_results=min(top_k, 20),
              where=where,
          )
          docs = results.get("documents", [[]])[0]
          ids = results.get("ids", [[]])[0]
          metas = results.get("metadatas", [[]])[0]
          distances = results.get("distances", [[]])[0]
          
          for doc, item_id, meta, dist in zip(docs, ids, metas, distances):
              if doc and str(doc).strip():
                  candidates.append({
                      "item_id": item_id,
                      "title": (meta or {}).get("name", item_id),
                      "category": (meta or {}).get("category", category),
                      "source": "chromadb_semantic",
                      "similarity_score": round(1 - float(dist), 3),
                      "metadata": meta or {},
                  })
          
          logger.info("[RETRIEVER] Category query returned %d candidates",
                      len(candidates))
      except Exception as e:
          logger.warning("[RETRIEVER] Category query failed: %s", e)
      
      # Attempt 2: if no results, query without category filter
      if not candidates:
          try:
              results = self.vector_store.query(
                  collection_name="items",
                  query_texts=[query_text],
                  n_results=min(top_k, 20),
              )
              docs = results.get("documents", [[]])[0]
              ids = results.get("ids", [[]])[0]
              metas = results.get("metadatas", [[]])[0]
              distances = results.get("distances", [[]])[0]
              
              for doc, item_id, meta, dist in zip(docs, ids, metas, distances):
                  if doc and str(doc).strip():
                      candidates.append({
                          "item_id": item_id,
                          "title": (meta or {}).get("name", item_id),
                          "category": (meta or {}).get("category", "unknown"),
                          "source": "chromadb_semantic_fallback",
                          "similarity_score": round(1 - float(dist), 3),
                          "metadata": meta or {},
                      })
              
              logger.info("[RETRIEVER] Fallback query returned %d candidates",
                          len(candidates))
          except Exception as e:
              logger.error("[RETRIEVER] Fallback query also failed: %s", e)
      
      return candidates[:top_k]

  Also add a method for user history retrieval:
  
  async def retrieve_user_history_items(
      self, user_id: str, top_k: int = 10
  ) -> list[dict]:
      """Retrieves items the user has reviewed before."""
      candidates = self._build_user_id_candidates(user_id)
      for candidate in candidates:
          try:
              results = self.vector_store.query(
                  collection_name="reviews",
                  query_texts=[""],
                  n_results=top_k,
                  where={"user_id": candidate},
              )
              ids = results.get("ids", [[]])[0]
              metas = results.get("metadatas", [[]])[0]
              if ids:
                  logger.info("[RETRIEVER] Found %d history items for %s",
                              len(ids), candidate)
                  return [
                      {
                          "item_id": (m or {}).get("item_id", ""),
                          "rating": float((m or {}).get("rating", 3.0)),
                          "category": (m or {}).get("category", ""),
                      }
                      for m in metas if m
                  ]
          except Exception:
              continue
      return []

FIX 4 — task_b/agent.py: wire retriever into recommend() method

The recommend() method must:
  1. Check if user is warm via _is_warm_user()
  2. If warm: call retriever.retrieve_candidates() with user's 
     preferred categories from ChromaDB metadata
  3. If cold: call cold_start handler BUT still try retriever first
  4. Always pass real candidates to the ranker
  5. Only use fake placeholders if retriever returns 0 results

Update thinking to reflect what actually happened:
  f"Retrieved {len(candidates)} real candidates from ChromaDB"
  f"Top candidate: {candidates[0]['title'] if candidates else 'none'}"

FIX 5 — task_b/agent.py: fix cross-domain logic

When enable_cross_domain=True:
  1. Fetch user metadata from ChromaDB to get their platform
  2. If platform != target_domain platform, call cross_domain bridge
  3. Log: "[AGENT_B] Cross-domain: {source_platform} → {target_domain}"
  4. The thinking array must mention cross-domain inference

<constraints>
- load_dotenv(override=True) must be first in task_b/main.py
- Retriever must query real ChromaDB "items" collection
- item_ids in response must be real ChromaDB IDs like 
  "yelp_7clCBgNbd-x2Wj96lZ6Mjw", not "explicit-1"
- thinking array must reflect real reasoning, not template strings
- explanation per item must reference the item's actual name 
  and category, not generic text
- Output all files in full with path headers
- No truncation
</constraints>

<expected_response_after_fix>
Test 1 should return items like:
  "item_id": "yelp_8c0r7olQSYGcws0bTd3ikw"
  "title": "Zesty Tsunami"
  "source": "chromadb_semantic"

thinking should say:
  "User has 65 stored reviews, treated as warm user"
  "Retrieved 20 candidates from ChromaDB items collection"
  "Top categories from history: Grocery, Arts & Crafts"
  "Reranking 20 candidates using LLM reasoning"
</expected_response_after_fix>