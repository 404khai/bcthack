<context>
Three bugs identified from recommend/chat endpoint testing.

BUG 1 — Rate limit handling (429 RESOURCE_EXHAUSTED)
The free tier limit is 20 requests/day for gemini-2.5-flash.
Running 9 chat turns × 2-3 LLM calls each = 18-27 calls = hits limit.

Current behavior: retries exhaust, raises RuntimeError, fallback triggers.
Better behavior: when 429 is hit, wait the retry delay and try once more,
then fall back gracefully with a clear log.

In shared/llm_client.py, in the exception handler:
  from google.genai.errors import ClientError
  
  If the error is a 429 ClientError:
    1. Extract retry delay from error message using regex:
       match = re.search(r"retry in ([\d.]+)s", str(error))
       wait_seconds = float(match.group(1)) if match else 35.0
    2. Log clearly: 
       logger.warning("[LLM] Rate limit hit. Waiting %.1fs...", wait_seconds)
    3. await asyncio.sleep(min(wait_seconds, 40))
    4. Try the call ONE more time
    5. If it fails again, raise so the fallback triggers

Also add FREE_TIER_MODE protection: if FREE_TIER_MODE=true in env,
add a 3-second delay between ALL LLM calls to stay under the 
per-minute limit, not just per-day.

BUG 2 — Cold user session turns not being saved
chat_naija_001 (cold user) shows "turns": [] despite 3 successful turns.
chat_warm_001 and chat_crossdomain_001 both save turns correctly.

The cold user path in task_b/agent.py takes a different code branch 
than the warm user path. The warm/cross-domain paths call 
conversation.add_turn() but the cold start branch does not.

Fix: in task_b/agent.py chat() method, ensure add_turn() is called
in ALL branches — warm, cold, and cross-domain — after the response 
is built. It should be the last step before returning, not inside 
each branch separately.

Move this to after all branch logic:
  # Always save turn regardless of strategy
  await self.conversation.add_turn(
      session_id=request.session_id,
      user_message=request.message,
      assistant_message=response.assistant_message,
      context={
          "category": request.request_context.category,
          "constraints": request.request_context.constraints,
          "mode": "chat",
      }
  )

BUG 3 — conversation.add_turn() may be sync not async
Check task_b/conversation.py — if add_turn() is a regular def not 
async def, the await above will fail silently.
Fix: make it async def add_turn() or remove the await.

Files to fix:
[PASTE shared/llm_client.py]
[PASTE task_b/agent.py]
[PASTE task_b/conversation.py]

Output all three files in full with path headers. No truncation.
</context>