<context>
Task A generate-review endpoint is working but has 3 quality issues 
to fix. Here are the problem files:

C:\Users\DanielsFega\Hackathons\bcthack\task_a\review_generator.py
C:\Users\DanielsFega\Hackathons\bcthack\task_a\persona_builder.py
C:\Users\DanielsFega\Hackathons\bcthack\shared\nigerian_adapter.py
C:\Users\DanielsFega\Hackathons\bcthack\shared\prompts.py
</context>

<secondary-context>
for task a generate-review, I used this payload, see what I got as response, and here is my terminal logs. 
  "user_persona": {
    "user_id": "lO1iq-f75hnPNZkTy3Zerg",
    "platform": "yelp",
    "review_history": [],
    "preferences": {}
  },
  "item_details": {
    "item_id": "new_item_001",
    "name": "Chicken Republic Lekki",
    "category": "Fast Food",
    "attributes": {
      "price_range": "budget",
      "location": "Lagos",
      "cuisine": "Nigerian Fast Food"
    }
  },
  "nigerian_mode": true,
  "nigerian_intensity": "medium"
}   

response:
{
  "user_id": "lO1iq-f75hnPNZkTy3Zerg",
  "item_id": "new_item_001",
  "rating": 3.9,
  "review_text": "I tried Chicken Republic Lekki in the Fast Food category and found it fairly balanced. What stood out most was price_range=budget, location=Lagos, cuisine=Nigerian Fast Food. It matches the kind of measured reaction I tend to have.",
  "confidence": 0.438,
  "style_notes": "Avg rating 3.50, rating std 0.00, avg length 60.0 words, formality 0.50, top phrases: no repeated phrases, Nigerian signals: none detected.",
  "style_fingerprint": {
    "avg_rating": 3.5,
    "rating_std": 0,
    "avg_review_length": 60,
    "vocabulary_size": 0,
    "top_phrases": [],
    "sentiment_profile": {
      "positive": 0.34,
      "neutral": 0.33,
      "negative": 0.33
    },
    "formality_score": 0.5,
    "nigerian_signals": []
  },
  "nigerian_mode": true
} 
 
INFO:     Uvicorn running on http://127.0.0.1:8001 (Press CTRL+C to quit)
INFO:     Started reloader process [20876] using WatchFiles
Failed to send telemetry event ClientStartEvent: capture() takes 1 positional argument but 3 were given
INFO:     Started server process [17812]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     127.0.0.1:57062 - "GET /docs HTTP/1.1" 200 OK
INFO:     127.0.0.1:57062 - "GET /openapi.json HTTP/1.1" 200 OK
INFO:     127.0.0.1:57111 - "GET /health HTTP/1.1" 200 OK
WARNING:  WatchFiles detected changes in 'debug_chroma.py'. Reloading...
INFO:     Shutting down
INFO:     Waiting for application shutdown.
INFO:     Application shutdown complete.
INFO:     Finished server process [17812]
WARNING:  WatchFiles detected changes in 'debug_chroma.py'. Reloading...
Process SpawnProcess-2:
Traceback (most recent call last):
  File "C:\Program Files\Python313\Lib\multiprocessing\process.py", line 313, in _bootstrap
    self.run()
    ~~~~~~~~^^
  File "C:\Program Files\Python313\Lib\multiprocessing\process.py", line 108, in run
    self._target(*self._args, **self._kwargs)
    ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\DanielsFega\Hackathons\bcthack\venv\Lib\site-packages\uvicorn\_subprocess.py", line 73, in subprocess_started
    sys.stdin = os.fdopen(stdin_fileno)  # pragma: full coverage        
                ~~~~~~~~~^^^^^^^^^^^^^^
  File "<frozen os>", line 1069, in fdopen
  File "<frozen codecs>", line 312, in __init__
KeyboardInterrupt
Failed to send telemetry event ClientStartEvent: capture() takes 1 positional argument but 3 were given
INFO:     Started server process [9548]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
Failed to send telemetry event ClientCreateCollectionEvent: capture() takes 1 positional argument but 3 were given
C:\Users\DanielsFega\.cache\chroma\onnx_models\all-MiniLM-L6-v2\onnx.ta 
Failed to send telemetry event CollectionQueryEvent: capture() takes 1 positional argument but 3 were given
INFO:     127.0.0.1:57198 - "POST /generate-review HTTP/1.1" 200 OK
</secondary-context>

<issues>

ISSUE 1 — vocabulary_size always returns 0
In task_a/persona_builder.py, the vocabulary_size field in 
StyleFingerprint is being set to 0.
Fix: count unique words across all review texts in the user's history.
  all_words = [word.lower() for review in review_history 
               for word in review.text.split()]
  vocabulary_size = len(set(all_words))

ISSUE 2 — Nigerian adapter not firing
The nigerian_mode=true and nigerian_intensity="medium" flags are being 
passed in the request but the output review has zero Nigerian flavor.
Investigate and fix the call chain:
  - In task_a/agent.py or task_a/review_generator.py, confirm that 
    when nigerian_mode=True, nigerian_adapter.adapt_review() is actually 
    being called on the final review_text AFTER generation
  - If it is being called, the prompt in shared/nigerian_adapter.py is 
    too weak — strengthen it
  - The medium intensity adapter prompt must instruct Gemini to:
      * Rewrite the review to sound like a Nigerian person wrote it
      * Add 2-3 references to Nigerian context naturally 
        (local food comparisons, Lagos references, value-for-money 
        consciousness, warm but direct tone)
      * Keep the same core sentiment and rating logic
      * Do NOT use Pidgin at medium intensity (only at full)
  - Add a log line: logger.info(f"Nigerian adapter called: {nigerian_mode}, intensity: {nigerian_intensity}")

ISSUE 3 — Review text is generic/templated
The main review generation prompt is producing fill-in-the-blank 
style text. Fix TASK_A_REVIEW_SYSTEM prompt in shared/prompts.py:

The prompt must:
  a) Open with the user's actual behavioral data, not generic instructions
  b) Include 2-3 example reviews from the user's history as few-shot 
     examples (even if short)
  c) Instruct the model to write as if it IS the user, not describe 
     what the user might say
  d) Specify: "Do not start with 'I tried' or 'I visited' — 
     vary the opening naturally"
  e) Specify exact length target based on user's avg_review_length
  f) If user has fewer than 3 reviews (cold user), instruct the model 
     to write a balanced, natural review for the item category

The review generation call in review_generator.py must:
  - Pass the user's actual review examples as part of the prompt 
    (fetch from ChromaDB if review_history is empty in the request)
  - Format them clearly as: "Here are examples of how this user writes: ..."
</issues>

<constraints>
- Do not change the request/response schema
- Do not change the endpoint path
- Keep all fixes backward compatible
- Output only the changed files in full
</constraints>