<context>
task_b/ranker.py has two bugs confirmed from logs.

BUG 1 — MAX_TOKENS truncates JSON response from Gemini
  Log: "Response: 236 chars, finish_reason=FinishReason.MAX_TOKENS"
  Log: "JSONDecodeError: Unterminated string starting at line 6 col 20"
  
  Cause: ranker sends 30 candidates asking for JSON array back.
  Each JSON item needs ~150-200 tokens minimum. 30 items × 200 = 6000 
  tokens needed but only 2048 provided. JSON gets cut mid-string.
  
  Fix A: reduce candidates sent to LLM from 30 to maximum 8
  Fix B: increase max_tokens to 4096
  Fix C: add JSON repair before parsing — if JSON is truncated, 
         attempt to salvage whatever complete items exist

BUG 2 — Item resolution fails for most history items
  Reviews store item_ids like "L3V21nAe-CicW2bvtNWa0g" (raw Yelp ID)
  Items collection only has 327 businesses from the sample.
  Most reviewed businesses are NOT in the items collection.
  
  Fix: when item cannot be resolved from items collection,
  fall back to semantic search — query the items collection 
  using the user's query text and categories instead of 
  trying to resolve specific item IDs.

Current ranker.py is attached above.
</context>

<fixes>

FIX 1 — ranker.py: limit candidates and fix JSON parsing

In the rerank() method, change this line:
  candidates=[candidate.model_dump() for candidate in candidates[:20]],
To:
  candidates=[candidate.model_dump() for candidate in candidates[:8]],

Change max_tokens from 2048 to 4096:
  response = await client.complete(
      system=...,
      user=...,
      max_tokens=4096,   # was 2048
  )

Replace _extract_json_payload() with a more robust version that 
salvages partial JSON:

  def _extract_json_payload(self, response: str) -> str:
      cleaned = response.strip()
      # Strip markdown fencing
      if cleaned.startswith("```json"):
          cleaned = cleaned[7:]
      elif cleaned.startswith("```"):
          cleaned = cleaned[3:]
      if cleaned.endswith("```"):
          cleaned = cleaned[:-3]
      cleaned = cleaned.strip()
      
      # Find the JSON array boundaries
      start = cleaned.find("[")
      if start == -1:
          return "[]"
      
      # Try full parse first
      candidate = cleaned[start:]
      try:
          json.loads(candidate)
          return candidate
      except json.JSONDecodeError:
          pass
      
      # Salvage complete objects from truncated array
      # Find all complete {...} objects within the array
      salvaged = []
      depth = 0
      obj_start = None
      i = start + 1  # skip opening [
      while i < len(candidate):
          ch = candidate[i]
          if ch == '{':
              if depth == 0:
                  obj_start = i
              depth += 1
          elif ch == '}':
              depth -= 1
              if depth == 0 and obj_start is not None:
                  obj_str = candidate[obj_start:i+1]
                  try:
                      json.loads(obj_str)
                      salvaged.append(obj_str)
                  except json.JSONDecodeError:
                      pass
                  obj_start = None
          i += 1
      
      if salvaged:
          logger.warning("[RANKER] Salvaged %d complete objects from truncated JSON",
                         len(salvaged))
          return "[" + ",".join(salvaged) + "]"
      
      logger.error("[RANKER] Could not salvage any JSON objects from response")
      return "[]"

FIX 2 — task_b/retriever.py: add semantic fallback when items not found

After retrieve_user_history_items() exhausts all ID candidates and 
most items are unresolved, add a semantic fallback that queries 
the items collection directly by embedding similarity:

  async def retrieve_semantic_candidates(
      self,
      query_text: str,
      category: str,
      top_k: int = 15,
  ) -> list[dict]:
      """Semantic search over items collection as fallback."""
      logger.info("[RETRIEVER] Semantic fallback query: %s", query_text[:60])
      
      try:
          results = self.vector_store.query(
              collection_name="items",
              query_texts=[query_text],
              n_results=top_k,
          )
          ids = results.get("ids", [[]])[0]
          metas = results.get("metadatas", [[]])[0]
          distances = results.get("distances", [[]])[0]
          docs = results.get("documents", [[]])[0]
          
          candidates = []
          for item_id, meta, dist, doc in zip(ids, metas, distances, docs):
              if not doc or not str(doc).strip():
                  continue
              similarity = max(0.0, min(1.0, 1.0 - (dist / 2.0)))
              candidates.append({
                  "item_id": item_id,
                  "title": (meta or {}).get("name", item_id),
                  "category": (meta or {}).get("category", category),
                  "source": "semantic_fallback",
                  "similarity_score": round(similarity, 3),
                  "metadata": meta or {},
              })
          
          logger.info("[RETRIEVER] Semantic fallback returned %d candidates",
                      len(candidates))
          return candidates
      except Exception as e:
          logger.error("[RETRIEVER] Semantic fallback failed: %s", e)
          return []

In task_b/agent.py, update the warm user path to use semantic 
fallback when history items resolve poorly:

  # After getting history_items
  resolved = [i for i in history_items if i.get("title") != i.get("item_id")]
  unresolved_ratio = 1 - (len(resolved) / max(len(history_items), 1))
  
  if unresolved_ratio > 0.5:
      # More than 50% unresolved — use semantic search instead
      logger.info("[AGENT_B] %.0f%% history unresolved, switching to semantic",
                  unresolved_ratio * 100)
      semantic = await self.retriever.retrieve_semantic_candidates(
          query_text=f"{request.query} {' '.join(top_categories)}",
          category=request.request_context.category,
          top_k=15,
      )
      candidates.extend(semantic)

<constraints>
- Max candidates sent to LLM ranker: 8 (not 20 or 30)
- max_tokens for ranker LLM call: 4096
- JSON salvage must never raise an exception — always return 
  valid JSON string (at minimum "[]")
- Semantic fallback similarity formula: max(0.0, min(1.0, 1-(dist/2)))
- Output all changed files in full with path headers
- No truncation
</constraints>

<expected_after_fix>
Logs should show:
  [RANKER] Calling LLM for 8 candidates    ← not 30
  [LLM] Response: 1240 chars, finish_reason=FinishReason.STOP  ← STOP not MAX_TOKENS
  [RANKER] LLM explanation sample: "Octopus Falafel Truck is an excellent..."
  [AGENT_B] 87% history unresolved, switching to semantic
  [RETRIEVER] Semantic fallback returned 15 candidates

Response item_ids should include real names like "Octopus Falafel Truck"
with genuine LLM-generated explanations.
</expected_after_fix>