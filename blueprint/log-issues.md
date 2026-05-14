<context>
We have three confirmed facts from ChromaDB inspection:

FACT 1 — User ID formats in ChromaDB:
  users collection IDs:   "yelp__BcWyKQL16ndpBdggh2kNA"
                          "amazon_A1K4G5YJDJQI6Q"  
                          "goodreads_72256c964486efe75b008e875c661715"
  (format: "{platform}_{original_id}" — original Yelp IDs start with "_")

FACT 2 — Review metadata user_id field format:
  Raw stored user_ids in reviews: ['yelp_IKbjLnfBQtEyVzEu8CuOLg', ...]
  (format: "yelp_{original_id}" — consistent with users collection)
  
  Query for "yelp__BcWyKQL16ndpBdggh2kNA" → 0 results (no match)
  Query for "_BcWyKQL16ndpBdggh2kNA"      → 3 results FOUND
  This means: reviews for this user are stored with user_id 
  metadata = "_BcWyKQL16ndpBdggh2kNA" (the original Yelp ID, 
  no platform prefix in the metadata field)

FACT 3 — API key is confirmed present in .env and readable by Python.
  The LLM is still showing "LLM unavailable" — meaning llm_client.py 
  is not reading the key at initialization time, likely because 
  load_dotenv() is not called before os.getenv() in that file.

Files to fix:
[PASTE shared/llm_client.py]
[PASTE shared/vector_store.py]
[PASTE task_a/agent.py]
[PASTE task_a/main.py]
</context>

<fixes>

FIX 1 — shared/llm_client.py: load dotenv at module level
Add these two lines at the very top, before any other imports:
  from dotenv import load_dotenv
  load_dotenv(override=True)

Then in the __init__ or wherever os.getenv("GEMINI_API_KEY") is called,
add a startup assertion:
  api_key = os.getenv("GEMINI_API_KEY")
  if not api_key:
      raise RuntimeError(
          "GEMINI_API_KEY is not set. "
          "Ensure it exists in your .env file and load_dotenv() runs first."
      )
  logger.info("[LLM] Gemini client initialized with key: %s...", api_key[:8])

FIX 2 — task_a/main.py: load dotenv at very top
First two lines of the file (before all other imports):
  from dotenv import load_dotenv
  load_dotenv(override=True)

FIX 3 — shared/vector_store.py: fix review query user_id matching

The review metadata stores user_id in TWO possible formats:
  Format A: "yelp_IKbjLnfBQtEyVzEu8CuOLg"  (platform + original_id)
  Format B: "_BcWyKQL16ndpBdggh2kNA"         (just original_id, for 
             users whose original_id already started with "_")

The agent queries with the full ChromaDB document ID like:
  "yelp__BcWyKQL16ndpBdggh2kNA"

Fix the review query method to try ALL of these candidate 
user_id values when filtering reviews:

  def _build_user_id_candidates(self, chroma_user_id: str) -> list[str]:
      """
      Given a ChromaDB user document ID, returns all possible values
      that the user_id metadata field in reviews might contain.
      
      ChromaDB user ID: "yelp__BcWyKQL16ndpBdggh2kNA"
      Candidates to try:
        1. "yelp__BcWyKQL16ndpBdggh2kNA"  (exact match)
        2. "_BcWyKQL16ndpBdggh2kNA"        (strip "yelp_" prefix)
        3. "yelp__BcWyKQL16ndpBdggh2kNA"   (already covered by 1)
      """
      candidates = [chroma_user_id]
      
      for platform in ("yelp_", "amazon_", "goodreads_"):
          if chroma_user_id.startswith(platform):
              stripped = chroma_user_id[len(platform):]
              if stripped not in candidates:
                  candidates.append(stripped)
              # Also try re-adding platform prefix in case of double prefix
              reprefixed = platform + stripped
              if reprefixed not in candidates:
                  candidates.append(reprefixed)
      
      return candidates

  Then in the actual query method, loop through candidates:
  
  def query_reviews_for_user(
      self, user_id: str, query_text: str, n_results: int = 5
  ) -> list[str]:
      candidates = self._build_user_id_candidates(user_id)
      logger.info("[CHROMADB] Trying %d user_id candidates: %s", 
                  len(candidates), candidates)
      
      for candidate in candidates:
          try:
              results = self.query(
                  collection_name="reviews",
                  query_texts=[query_text],
                  n_results=n_results,
                  where={"user_id": candidate},
              )
              docs = results.get("documents", [[]])[0]
              valid = [d for d in docs if d and str(d).strip()]
              if valid:
                  logger.info("[CHROMADB] Found %d reviews with candidate: %s",
                              len(valid), candidate)
                  return valid
          except Exception as e:
              logger.warning("[CHROMADB] Query failed for candidate %s: %s", 
                           candidate, e)
              continue
      
      logger.warning("[CHROMADB] No reviews found for any candidate of: %s", 
                     user_id)
      return []

FIX 4 — task_a/agent.py: use real ChromaDB metadata to rebuild fingerprint

When the agent fetches a user from ChromaDB and the user exists,
it must rebuild StyleFingerprint from stored metadata, not defaults.

After fetching user metadata from ChromaDB users collection:
  
  from shared.user_profile import StyleFingerprint, UserProfile
  
  meta = chroma_result["metadatas"][0]  # actual field name may vary
  
  # Parse top_phrases from comma-separated string
  raw_phrases = meta.get("top_phrases", "") or ""
  top_phrases = [p.strip() for p in raw_phrases.split(",") if p.strip()]
  
  # Parse nigerian_signals from comma-separated string  
  raw_signals = meta.get("nigerian_signals", "") or ""
  nigerian_signals = [s.strip() for s in raw_signals.split(",") if s.strip()]
  
  # Parse preferred_categories
  raw_cats = meta.get("preferred_categories", "") or ""
  preferred_categories = [c.strip() for c in raw_cats.split(",") if c.strip()]
  
  fingerprint = StyleFingerprint(
      avg_rating=float(meta.get("avg_rating", 3.5)),
      rating_std=float(meta.get("rating_std", 0.0)),
      avg_review_length=float(meta.get("avg_review_length", 60.0)),
      vocabulary_size=int(meta.get("vocabulary_size", 0)),
      top_phrases=top_phrases,
      sentiment_profile={
          "positive": float(meta.get("sentiment_positive", 0.34)),
          "neutral":  float(meta.get("sentiment_neutral",  0.33)),
          "negative": float(meta.get("sentiment_negative", 0.33)),
      },
      formality_score=float(meta.get("formality_score", 0.5)),
      nigerian_signals=nigerian_signals,
  )
  
  NOTE: Check UserProfile.to_metadata() in shared/user_profile.py for 
  the EXACT field names stored — use those exactly. The sentiment fields 
  may be stored as "sentiment_positive" or just inside a nested dict.
  Match whatever to_metadata() actually writes.

  Add this log after rebuilding:
  logger.info("[AGENT] Rebuilt fingerprint from ChromaDB: avg_rating=%s, 
              review_count=%s, vocab=%s",
              fingerprint.avg_rating,
              meta.get("review_count"),
              fingerprint.vocabulary_size)

<constraints>
- load_dotenv(override=True) must be the first thing that runs 
  in both main.py and llm_client.py
- Do not change any request/response schemas
- The query_reviews_for_user method must be the single point of 
  truth for review retrieval — update all callers to use it
- Output all changed files in full with path headers
- No truncation
</constraints>

<expected_terminal_after_fix>
INFO: [LLM] Gemini client initialized with key: AIzaSy...
INFO: [AGENT] Starting for user: yelp__BcWyKQL16ndpBdggh2kNA
INFO: [AGENT] Rebuilt fingerprint from ChromaDB: avg_rating=4.2, 
              review_count=65, vocab=1847
INFO: [CHROMADB] Trying 2 user_id candidates: ['yelp__BcWyKQL16ndpBdggh2kNA', 
                 '_BcWyKQL16ndpBdggh2kNA']
INFO: [CHROMADB] Found 5 reviews with candidate: _BcWyKQL16ndpBdggh2kNA
INFO: [GENERATOR] Using LLM path
INFO: [GENERATOR] Few-shot examples count: 5
INFO: [GENERATOR] Raw LLM output: Honestly this place caught me off guard...
</expected_terminal_after_fix>