<context>
Task A has three confirmed bugs from terminal log analysis.

Logs show:
1. "[GENERATOR] Using fallback path — reason: LLM unavailable"
   → GEMINI_API_KEY not being loaded
   
2. "[CHROMADB] Query result count: 0" for both candidate user IDs
   → User ID format mismatch between stored reviews and query

3. UserProfile returned from ChromaDB has review_history=[] and 
   default fingerprint values (avg_rating=3.5, all defaults)
   → Agent is building a blank UserProfile instead of reading 
     the real stored fingerprint from metadata

Files to fix:
[PASTE task_a/main.py]
[PASTE task_a/agent.py]  
[PASTE shared/llm_client.py]
[PASTE shared/vector_store.py]
</context>

<fixes>

FIX 1 — Load .env before anything else in task_a/main.py
At the very top of task_a/main.py, before all other imports:
  from dotenv import load_dotenv
  load_dotenv(override=True)

Then add a startup log to confirm the key loaded:
  import os
  logger.info(f"GEMINI_API_KEY loaded: {'yes' if os.getenv('GEMINI_API_KEY') else 'NO - KEY MISSING'}")

FIX 2 — In shared/llm_client.py, add the same dotenv load at top:
  from dotenv import load_dotenv
  load_dotenv(override=True)

And add a clear error if key is missing:
  api_key = os.getenv("GEMINI_API_KEY")
  if not api_key:
      raise ValueError(
          "GEMINI_API_KEY environment variable not set. "
          "Add it to your .env file and restart the server."
      )

FIX 3 — In task_a/agent.py, fix UserProfile reconstruction from ChromaDB.

Currently the agent fetches user metadata from ChromaDB but builds 
a UserProfile with empty review_history and default fingerprint.
The fix: when fetching a user from ChromaDB, reconstruct StyleFingerprint 
from the stored metadata fields directly.

In the method that fetches user from ChromaDB (likely fetch_user_profile 
or similar), after getting metadata from ChromaDB:

  metadata = chroma_result["metadatas"][0]
  
  # Rebuild fingerprint from stored metadata instead of defaulting
  fingerprint = StyleFingerprint(
      avg_rating=float(metadata.get("avg_rating", 3.5)),
      rating_std=float(metadata.get("rating_std", 0.0)),
      avg_review_length=float(metadata.get("avg_review_length", 60.0)),
      vocabulary_size=int(metadata.get("vocabulary_size", 0)),
      top_phrases=metadata.get("top_phrases", "").split(",") 
                  if metadata.get("top_phrases") else [],
      sentiment_profile={
          "positive": float(metadata.get("sentiment_positive", 0.34)),
          "neutral": float(metadata.get("sentiment_neutral", 0.33)),
          "negative": float(metadata.get("sentiment_negative", 0.33)),
      },
      formality_score=float(metadata.get("formality_score", 0.5)),
      nigerian_signals=metadata.get("nigerian_signals", "").split(",")
                       if metadata.get("nigerian_signals") else [],
  )

Check what field names are actually stored in ChromaDB metadata by 
looking at UserProfile.to_metadata() in shared/user_profile.py — 
use those exact field names.

FIX 4 — In shared/vector_store.py, fix the reviews query to handle 
the yelp__ double-underscore user ID format.

The stored review metadata user_id field may differ from the ChromaDB 
document ID. Add a fallback query that searches without any platform prefix:

  def query_reviews_for_user(self, user_id: str, category: str, n: int):
      # Try exact match first
      results = self._query_with_filter(user_id, category, n)
      if results:
          return results
      
      # Try stripping known platform prefixes
      for prefix in ("yelp_", "amazon_", "goodreads_"):
          if user_id.startswith(prefix):
              stripped = user_id[len(prefix):]
              results = self._query_with_filter(stripped, category, n)
              if results:
                  return results
      
      return []

FIX 5 — Verify python-dotenv is installed
Add to task_a/requirements.txt if not already present:
  python-dotenv>=1.0.0
</fixes>

<verification>
After fixes, the terminal should show these log lines on next request:
  "GEMINI_API_KEY loaded: yes"
  "[GENERATOR] Using LLM path"  
  "[GENERATOR] System prompt length: [number > 500]"
  "[GENERATOR] Raw LLM output: [actual generated text, not template]"
  
And the response review_text should NOT start with "I tried" and 
should be 3-5 sentences of natural language.
</verification>

<constraints>
- load_dotenv() must be called before any os.getenv() calls
- Do not change request/response schemas
- Output all changed files in full with path headers
</constraints>