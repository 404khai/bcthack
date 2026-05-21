<role>
You are a technical writer and ML engineer who has won multiple AI 
hackathons. You write solution papers that read like engineering 
postmortems — precise, honest, full of insight. Never pad with fluff.
</role>

<task>
Generate a complete content brief for a 4-6 page solution paper 
for TASK A (User Modeling) of the DSN x BCT LLM Agent Hackathon.

The paper covers ONLY Task A. It must read like a senior engineer 
wrote it — deliberate decisions, real obstacles, genuine insights.
</task>

<known_facts_from_implementation>
These are confirmed real facts from our implementation and debugging:

ARCHITECTURE:
- Two microservices: Task A on port 8001, Task B on port 8002
- Shared ChromaDB: users(394), items(499), reviews(5212) documents
- Embedding model: sentence-transformers all-MiniLM-L6-v2
- LLM: Gemini 2.5 Flash via google-genai SDK
- Datasets ingested (sample mode):
    Yelp: 100 users, 327 items, 372 reviews, 125 test reviews
    Amazon: 100 users, 144 items, 1677 reviews
    Goodreads: 100 users, 28 items, 2702 reviews, 581 test reviews

TASK A PIPELINE (confirmed working):
- Step 1: Fetch user from ChromaDB users collection by user_id
- Step 2: Rebuild StyleFingerprint from metadata + document text
  Fields: avg_rating, rating_std, avg_review_length, vocabulary_size,
          top_phrases, sentiment_profile, formality_score, nigerian_signals
  Computed: n-gram phrase extraction, lexicon-based sentiment,
            formality ratio, Nigerian term detection
- Step 3: Retrieve up to 5 example reviews via ChromaDB with 
  user_id candidate matching
- Step 4: Build system prompt with fingerprint + few-shot examples
- Step 5: Gemini generates review (max_tokens=1024)
- Step 6: NigerianAdapter post-processes if nigerian_mode=True
  Three intensity levels: light, medium, full

REAL BUGS WE FIXED (each is an engineering insight):
1. Wrong LLM client class name (AnthropicLLMClient vs GeminiLLMClient)
   — caused silent fallback to template for every request
2. load_dotenv() not called before os.getenv() 
   — GEMINI_API_KEY read as None, LLM unavailable
3. ChromaDB path mismatch (chroma_db/ vs chroma_data/)
   — all collections appeared empty
4. User ID double-prefix bug: Yelp user IDs start with "_" so 
   ingestion stored them as "yelp__userId" (double underscore).
   Reviews were stored with user_id="_userId" (no platform prefix).
   Fix: candidate-based lookup tries multiple ID formats.
5. StyleFingerprint fields (rating_std, sentiment, formality, 
   top_phrases) stored in ChromaDB document text, not metadata.
   Fix: regex parsing of document text on each request.
6. Nigerian adapter makes second LLM call that truncates mid-sentence
   at medium/full intensity — known limitation, not fully resolved.

CONFIRMED WORKING TEST RESULTS:
- User yelp__BcWyKQL16ndpBdggh2kNA (65 reviews):
    avg_rating: 3.615, avg_review_length: 78.09, vocabulary_size: 1632
    Generated review: "Stopped by Zesty Tsunami in Las Vegas for a 
    quick lunch. The Hawaiian Fusion idea sounded promising..."
- Amazon user amazon_A1K4G5YJDJQI6Q (40 reviews, Electronics):
    avg_rating: 2.8, avg_review_length: 285.8, vocabulary_size: 1788
    Generated: "Having a portable charger is pretty much essential 
    these days, so I picked up the Anker 20000mAh power bank..."
- Nigerian mode: generates Lekki/Lagos references naturally

RATE LIMITING:
- Gemini free tier: 20 requests/day
- Added Groq (llama-3.3-70b-versatile) as fallback on 429
- FREE_TIER_MODE=true adds 2-3s delay between calls

EVALUATION METHODOLOGY (not yet run — describe the approach):
- ROUGE-1, ROUGE-L: n-gram overlap vs held-out user reviews
- BERTScore-F1: semantic similarity vs held-out reviews  
- RMSE: predicted rating vs actual held-out rating
- Test split: last 20% of each user's reviews (deterministic)
- 706 total test reviews across platforms
</known_facts_from_implementation>

<codebase_to_scan>
Read these files for exact implementation details to add to the paper:
shared/user_profile.py       — StyleFingerprint dataclass, all fields
shared/llm_client.py         — Gemini client, retry logic, Groq fallback
shared/nigerian_adapter.py   — intensity levels, adaptation logic
shared/prompts.py            — TASK_A_REVIEW_SYSTEM prompt content
task_a/agent.py              — full pipeline, timing logs
task_a/persona_builder.py    — fingerprint extraction
task_a/review_generator.py   — LLM call, fallback, few-shot retrieval
task_a/rating_predictor.py   — rating prediction method
task_a/evaluator.py          — metrics implementation
</codebase_to_scan>

<paper_structure>

SECTION 1 — Problem Framing (0.5 pages)
Core argument: User modeling is a behavioral simulation problem,
not a preference aggregation problem.

Write:
- What Task A asks for in engineering terms: given a user's review 
  history, simulate what they would write and rate for an unseen item
- The key insight: rating behavior has two components — central 
  tendency (avg_rating) and consistency (rating_std). A user with 
  avg=3.5, std=1.2 is volatile; avg=4.2, std=0.3 is a reliable 
  enthusiast. These predict different reviews.
- One differentiator from baseline: few-shot grounding with the 
  user's own historical reviews as examples

SECTION 2 — System Architecture (0.75 pages)
Include the ASCII diagram. Document:
- Why two separate services (separation of concerns, independent scaling)
- Why ChromaDB over alternatives
- Why Gemini 2.5 Flash (1M context, free tier, sufficient quality)
- Dataset ingestion pipeline: three processors, streaming JSON parsing,
  80/20 train/test split per user, deterministic (sorted by date)

SECTION 3 — StyleFingerprint: Behavioral DNA (1 page)
This is the core contribution of Task A. Document thoroughly:

3a. All 8 fields with HOW each is computed (extract from user_profile.py)
3b. The storage challenge: ChromaDB metadata is flat key-value.
    StyleFingerprint has nested fields (sentiment dict, phrases list).
    Solution: encode lists as comma-separated strings in metadata,
    encode remaining fields in the searchable document text.
    Consequence: requires regex parsing on retrieval.
    Show the actual regex patterns used.
3c. The double-prefix bug — explain fully as an engineering case study.
    This demonstrates real production thinking.

SECTION 4 — Review Generation Pipeline (1 page)

4a. The 6-step pipeline (extract exact flow from agent.py)
4b. Few-shot retrieval: why pulling the user's own reviews as 
    examples works better than generic prompting. The candidate 
    user_id matching strategy (tries 2-3 ID formats).
4c. The system prompt design (extract from prompts.py):
    - What behavioral signals are encoded
    - How length target is communicated (min_words, max_words)
    - How formality is communicated
4d. Rating prediction: extract the exact method from rating_predictor.py
4e. The fallback template: document it honestly.
    "I tried {item} in the {category} category..."
    Explain: this was the entire output before fixing 3 bugs.
    Now only fires if Gemini AND Groq both fail.

SECTION 5 — Nigerian Contextualization (0.5 pages)
5a. Detection: NIGERIAN_TERMS lexicon (list terms from user_profile.py)
5b. Three intensity levels — what each does differently
5c. The second-LLM-call architecture and its truncation problem
5d. Why this matters: explicit bonus criterion + cultural relevance

SECTION 6 — Experiments & Evaluation (0.75 pages)
6a. Evaluation methodology (ROUGE, BERTScore, RMSE)
6b. Three natural ablations from our debugging journey:
    
    Ablation 1: Template vs LLM
    Before: deterministic template for every user regardless of history
    After: LLM with few-shot grounding from user's own reviews
    Observable difference: template produces identical structure;
    LLM produces varied, contextually appropriate text
    
    Ablation 2: Empty fingerprint vs real fingerprint
    Before: all users got avg_rating=3.5, std=0.0 (ChromaDB path bug)
    After: real values like avg_rating=3.615, std=1.02, vocab=1632
    Impact: system prompt now encodes real behavioral variance
    
    Ablation 3: No few-shot vs 5 few-shot examples
    Before: 0 examples (user_id lookup failed due to prefix bug)
    After: 5 real user reviews used as few-shot context
    Observable: review text now mimics user's actual writing patterns

6c. Rate limiting as a real-world constraint:
    20 req/day Gemini free tier forces architectural discipline.
    Each pipeline component that makes an LLM call compounds the quota.
    Fix: Groq fallback (llama-3.3-70b-versatile) on 429 response.
    Engineering lesson: multi-provider LLM routing is not optional 
    in production — it's a reliability requirement.

SECTION 7 — Known Limitations & Future Work (0.5 pages)
Limitations (honest, specific):
1. Nigerian adapter truncation at medium/full intensity
2. StyleFingerprint stored partly in document text requiring regex
3. 706 test reviews from 3-dataset sample — small eval set
4. Amazon reviews: batch insert bug lost some test split records
5. Latency: 10-15 seconds per request (Gemini + free tier delay)

Future Work (genuine):
1. Run full ingestion — 100 users is too few for meaningful eval
2. Store all StyleFingerprint fields as explicit ChromaDB metadata
3. Fine-tune embedding model on domain-specific review text
4. Stream LLM output to reduce perceived latency
5. User feedback loop: re-ingest ratings from generated reviews

</paper_structure>

<output_format>
For each section output:

SECTION [N]: [TITLE]
Target length: [X] pages
Core argument: [one sentence]

PROSE:
[Write the actual prose as it would appear in the paper.
Use active voice. Be specific. Reference real variable names,
real numbers, real file names where relevant.]

KEY INSIGHT LINE:
[One sentence that captures the most important idea in this section]
</output_format>

<tone>
Engineer to engineer. Active voice. Honest about failures.
Real numbers over round numbers. Never say "robust" or "seamless".
</tone>