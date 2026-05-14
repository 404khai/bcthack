<context>
Two confirmed bugs in task_a/review_generator.py causing every request 
to use the hardcoded fallback template instead of the LLM.

Here are the two files to fix:
C:\Users\DanielsFega\Hackathons\bcthack\shared\llm_client.py
C:\Users\DanielsFega\Hackathons\bcthack\task_a\review_generator.py
</context>

<bugs>

BUG 1 — Wrong LLM client import and instantiation
In review_generator.py:
  Line 8:  from shared.llm_client import AnthropicLLMClient
  Line 96: self._llm_client = AnthropicLLMClient(model=CLAUDE_MODEL_NAME)

The class was renamed during the Gemini refactor. Check shared/llm_client.py 
for the actual class name (likely GeminiLLMClient or LLMClient) and update:
  1. The import on line 8
  2. The instantiation on line 96
  3. The type hint on __init__ parameter: llm_client: AnthropicLLMClient | None
  4. Remove the CLAUDE_MODEL_NAME constant — Gemini model is configured 
     inside llm_client.py already

Also fix the silent exception swallowing on the LLM call:
Change this:
  try:
      review_text = await client.generate_text(...)
      ...
  except Exception:
      pass

To this:
  try:
      review_text = await client.generate_text(...)
      ...
  except Exception as e:
      logger.error("[GENERATOR] LLM call failed: %s", e, exc_info=True)
      # fall through to fallback

This way we can see actual errors instead of silent failures.

BUG 2 — Double-prefixed user ID in ChromaDB lookup
In review_generator.py _candidate_user_ids() method:

Current broken code:
  candidates = [user_profile.user_id]
  prefixed = f"{user_profile.platform}_{user_profile.user_id}"
  
If user_id is already "yelp__BcWyKQL16ndpBdggh2kNA" and platform is "yelp",
this produces "yelp_yelp__BcWyKQL16ndpBdggh2kNA" which never matches ChromaDB.

Fix _candidate_user_ids() to return these candidates in order:
  1. user_profile.user_id as-is (already correct for most cases)
  2. f"{platform}_{user_id}" only if user_id does NOT already 
     start with f"{platform}_"
  3. The raw user_id without any platform prefix, in case it was 
     stored without prefix

New implementation:
  def _candidate_user_ids(self, user_profile: UserProfile) -> list[str]:
      uid = user_profile.user_id
      platform = user_profile.platform
      candidates = [uid]
      
      # Only add prefixed version if not already prefixed
      if not uid.startswith(f"{platform}_"):
          candidates.append(f"{platform}_{uid}")
      
      # Also try stripping existing prefix as fallback
      if uid.startswith(f"{platform}_"):
          candidates.append(uid[len(platform)+1:])
      
      return candidates

BUG 3 — LLM client method name mismatch
The call in review_generator.py uses:
  client.generate_text(system_prompt=..., user_prompt=..., ...)

Check shared/llm_client.py for the actual method name on the Gemini client.
It may be named complete(), generate(), or call().
Update the call in review_generator.py to match the actual method name 
and parameter names exactly as defined in llm_client.py.
</bugs>

<constraints>
- Do not change the public interface of ReviewGenerator
- Do not change schemas.py
- Keep the fallback template as last resort — it should only fire if 
  the LLM genuinely fails, not because of import errors
- Output both files in full with path headers
- Add one log line confirming which path was taken:
  logger.info("[GENERATOR] Using LLM path") 
  logger.info("[GENERATOR] Using fallback path — reason: %s", reason)
</constraints>