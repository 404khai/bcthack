<context>
Three bugs remain in Task A after latest fixes.

BUG 1 — Nigerian adapter truncates review (critical)
The NigerianContextAdapter makes a second LLM call to adapt the review.
This second call is truncating the output to ~15 words.

Evidence from terminal logs:
  First LLM call generates full review text
  Second call (adapter) overwrites it with truncated version
  "I was in Lekki and just needed something quick to eat, so" — cuts mid-sentence

Also terminal logs didn't show up in my latest test run, look into that minor issue as well
The adapter's LLM call almost certainly has max_tokens set too low,
likely 100-200. It needs to be at least 1024.

BUG 2 — All reviews truncate mid-sentence (moderate)
Even without Nigerian mode, reviews end abruptly:
  "the overall flavor profile was a bit understated"  ← no period, cuts off
  "keeping my devices"  ← cuts off mid-thought

This means the first LLM call also hits its token limit.
The fix from last round set max_tokens=1024 on the generator call
but may not have updated the underlying llm_client default.

BUG 3 — Fingerprint fields still showing defaults (minor)
Despite the document text containing real values:
  "rating deviation 1.02, formality 0.48, 
   positive=0.74, neutral=0.23, negative=0.03"
The response still shows:
  rating_std: 0, formality_score: 0.5, 
  sentiment: {positive:0.34, neutral:0.33, negative:0.33}

The regex parsing from last fix is not running or not matching.

Files to fix:
shared/nigerian_adapter.py
shared/llm_client.py
task_a/agent.py
</context>

<fixes>

FIX 1 — shared/nigerian_adapter.py: increase token limit on adapter call

Find every call to the LLM inside NigerianContextAdapter.adapt_review()
and change max_tokens to 1024 minimum.

Also add these log lines to the adapter:
  logger.info("[NIGERIAN] Input review length: %d chars", len(review_text))
  logger.info("[NIGERIAN] Output review length: %d chars", len(adapted))
  logger.info("[NIGERIAN] LLM finish reason: %s", finish_reason)

The adapter prompt must also explicitly instruct the model:
  "Write a COMPLETE review of similar length to the input. 
   Do not truncate. End with a complete sentence."

FIX 2 — shared/llm_client.py: set hard minimum on max_output_tokens

In the generate_text / complete / call method, enforce:
  effective_max_tokens = max(max_tokens, 1024)

And log the actual value being sent:
  logger.info("[LLM] Sending request: max_output_tokens=%d", effective_max_tokens)

Also log finish_reason on every response:
  finish_reason = response.candidates[0].finish_reason
  logger.info("[LLM] Response: %d chars, finish_reason=%s", 
              len(text), finish_reason)
  if str(finish_reason) in ("MAX_TOKENS", "2"):
      logger.warning("[LLM] TRUNCATED by token limit — increase max_output_tokens")

FIX 3 — task_a/agent.py: fix regex parsing of document text

The document text format is exactly:
  "User _BcWyKQL16ndpBdggh2kNA on yelp prefers Grocery, Arts & Crafts, 
   Fruits & Veggies, Flowers & Gifts, Sewing & Alterations. 
   Average rating 3.62 with rating deviation 1.02. 
   Average review length 78.1 words, vocabulary size 1632, formality 0.48. 
   Top phrases: we were, year old, if you, we had, very nice. 
   Sentiment profile: positive=0.74, neutral=0.23, negative=0.03."

Fix the regex patterns to match this exact format:

  import re

  # rating_std — matches "rating deviation 1.02"
  m = re.search(r"rating deviation ([\d.]+)", document_text)
  rating_std = float(m.group(1)) if m else 0.0

  # formality — matches "formality 0.48"  
  m = re.search(r"formality ([\d.]+)", document_text)
  formality_score = float(m.group(1)) if m else 0.5

  # top_phrases — matches "Top phrases: we were, year old, if you, we had, very nice."
  m = re.search(r"Top phrases: ([^.]+)\.", document_text)
  top_phrases = []
  if m and m.group(1).strip().lower() != "none":
      top_phrases = [p.strip() for p in m.group(1).split(",") if p.strip()]

  # sentiment — matches "positive=0.74, neutral=0.23, negative=0.03"
  sentiment_profile = {"positive": 0.34, "neutral": 0.33, "negative": 0.33}
  for sentiment_key in ("positive", "neutral", "negative"):
      m = re.search(rf"{sentiment_key}=([\d.]+)", document_text)
      if m:
          sentiment_profile[sentiment_key] = float(m.group(1))

Add a log line after parsing to confirm it worked:
  logger.info(
      "[AGENT] Parsed from document: rating_std=%s, formality=%s, "
      "phrases=%s, sentiment=%s",
      rating_std, formality_score, top_phrases, sentiment_profile
  )

<constraints>
- The minimum max_output_tokens anywhere in the codebase must be 1024
- Nigerian adapter must produce output of similar length to input
- Do not change request/response schemas  
- Output all three files in full with path headers
- No truncation
</constraints>

<expected_after_fix>
Test 2 Nigerian mode response should be 4-6 complete sentences, ending
with a period, with Nigerian cultural references naturally woven in.

Terminal should show:
  [LLM] Sending request: max_output_tokens=1024
  [LLM] Response: 387 chars, finish_reason=STOP   ← STOP not MAX_TOKENS
  [NIGERIAN] Input review length: 387 chars
  [NIGERIAN] Output review length: 412 chars       ← similar length
  [AGENT] Parsed from document: rating_std=1.02, formality=0.48,
          phrases=['we were', 'year old', 'if you'], sentiment={positive:0.74...}
</expected_after_fix>