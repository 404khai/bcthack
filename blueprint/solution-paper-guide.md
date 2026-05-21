<role>
You are a technical writer and ML engineer who has won multiple AI hackathons. 
You write solution papers that read like engineering postmortems — precise, 
honest, and full of insight. You never pad with fluff.
</role>

<task>
Generate a complete, detailed outline and content brief for a 4-6 page 
solution paper for the DSN x BCT LLM Agent Hackathon.

The paper must read like it was written by a senior engineer who deeply 
understood the problem, made deliberate decisions, hit real obstacles, 
and extracted genuine insights from debugging. NOT like a project report.

Scan the entire codebase and extract real details for each section below.
</task>

<codebase_to_scan>
Read these files and extract actual implementation details:

shared/llm_client.py          — LLM client, model used, retry logic
shared/vector_store.py        — ChromaDB setup, query patterns
shared/user_profile.py        — StyleFingerprint fields, build_style_fingerprint()
shared/embeddings.py          — embedding model used
shared/nigerian_adapter.py    — adaptation logic, intensity levels
shared/prompts.py             — all prompt templates

task_a/agent.py               — full pipeline flow
task_a/persona_builder.py     — fingerprint extraction logic
task_a/review_generator.py    — LLM call, fallback logic, few-shot retrieval
task_a/rating_predictor.py    — rating prediction method
task_a/evaluator.py           — metrics used

task_b/agent.py               — reasoning loop, warm/cold detection
task_b/retriever.py           — retrieval strategies
task_b/cold_start.py          — cold start handling
task_b/cross_domain.py        — cross-domain bridge
task_b/conversation.py        — session management
task_b/ranker.py              — LLM reranking, JSON recovery

data/yelp_processor.py
data/amazon_processor.py
data/goodreads_processor.py
data/ingest.py                — ingestion stats, ChromaDB collections

eval/run_task_a_eval.py
eval/run_task_b_eval.py
</codebase_to_scan>

<paper_structure>
Generate a section-by-section content brief. For each section provide:
  1. The exact prose to write (or detailed bullet points if prose TBD)
  2. Any real numbers, code snippets, or architecture details to include
  3. What insight or argument this section is making

SECTION 1 — Problem Framing (0.5 pages)
Extract and articulate:
- What the two tasks are actually asking for in engineering terms
- The core insight that drove our approach:
  "Most systems model users as static preference vectors. We model them 
   as dynamic behavioral agents with style fingerprints."
- One sentence on what differentiates our approach from a baseline

SECTION 2 — System Architecture (1 page)
Extract from codebase:
- The two-service design (Task A port 8001, Task B port 8002)
- Shared infrastructure: ChromaDB collections (users, items, reviews), 
  their document counts after ingestion (394 users, 499 items, 5212 reviews)
- Embedding model used (from shared/embeddings.py)
- LLM used: Gemini 2.5 Flash (from shared/llm_client.py)
- The three datasets and their processing:
    Yelp: 100 users, 327 items, 372 reviews (sample)
    Amazon: 100 users, 144 items, 1677 reviews (sample)
    Goodreads: 100 users, 28 items, 2702 reviews (sample)
- Why ChromaDB: persistent, no external server, metadata filtering
- Why Gemini 2.5 Flash: 1M context window, free tier, fast
- Include this ASCII diagram:

  ┌─────────────────────────────────────────────────┐
  │              Shared Infrastructure               │
  │  ChromaDB: users(394) items(499) reviews(5212)  │
  │  Embeddings: sentence-transformers MiniLM-L6-v2 │
  │  LLM: Gemini 2.5 Flash (google-genai SDK)       │
  └──────────────┬──────────────────────┬────────────┘
                 │                      │
  ┌──────────────▼──────────┐  ┌───────▼────────────────┐
  │   Task A: User Modeling  │  │  Task B: Recommendation │
  │   POST /generate-review  │  │  POST /recommend        │
  │   port 8001              │  │  POST /recommend/chat   │
  │                          │  │  port 8002              │
  │  PersonaBuilder          │  │  ReasoningAgent         │
  │  StyleFingerprint        │  │  MultiSourceRetriever   │
  │  ReviewGenerator (LLM)   │  │  LLMRanker              │
  │  RatingPredictor         │  │  ColdStartHandler       │
  │  NigerianAdapter         │  │  CrossDomainBridge      │
  └──────────────────────────┘  │  ConversationManager    │
                                └────────────────────────┘

SECTION 3 — Task A: User Modeling Approach (1 page)
Extract from task_a/ files and document these real implementation details:

3a. Style Fingerprint Extraction (from shared/user_profile.py)
    List the exact fields in StyleFingerprint dataclass:
    avg_rating, rating_std, avg_review_length, vocabulary_size,
    top_phrases, sentiment_profile, formality_score, nigerian_signals
    
    Explain HOW each is computed — extract the actual logic:
    - avg_rating: mean of all historical ratings
    - rating_std: standard deviation (behavioral consistency signal)
    - top_phrases: 2-3 word n-grams filtered by stopwords, top 8
    - sentiment: positive/neutral/negative word matching against lexicons
    - formality: ratio of formal vs informal vocabulary
    - nigerian_signals: detection of Naija terms from curated lexicon

3b. Review Generation Pipeline
    Extract the actual flow from task_a/agent.py and review_generator.py:
    Step 1: Fetch user profile from ChromaDB users collection
    Step 2: Rebuild StyleFingerprint from stored metadata + document text
            (explain the regex parsing from document text for fields not 
             in metadata: rating_std, formality, top_phrases, sentiment)
    Step 3: Retrieve 5 example reviews via ChromaDB query with user_id 
            candidate matching (explain the double-prefix bug we fixed)
    Step 4: Build system prompt with fingerprint + few-shot examples
    Step 5: Gemini generates review text (max_tokens=1024)
    Step 6: NigerianAdapter post-processes if nigerian_mode=True

3c. Rating Prediction
    Extract from task_a/rating_predictor.py — how is the rating predicted?
    Document the actual method used.

3d. Key Engineering Challenge — Document this real bug and fix:
    "The user ID stored in ChromaDB users collection used a double-prefix 
     format (yelp__BcWyKQL16ndpBdggh2kNA) because Yelp user IDs themselves 
     begin with an underscore. The reviews collection stored these under the 
     original ID (_BcWyKQL16ndpBdggh2kNA). This required a candidate-based 
     lookup strategy that tries multiple ID formats before failing."
    
    This is a real engineering insight worth highlighting.

SECTION 4 — Task B: Recommendation Approach (1 page)
Extract from task_b/ files:

4a. Reasoning-First Agent Loop
    Extract the actual thinking[] array generation from agent.py
    Show the real steps:
    - Query interpretation
    - Warm/cold detection (review_count >= 3 threshold from ChromaDB)
    - Strategy selection: warm_history_content_hybrid vs cold_start_hybrid
      vs hybrid_cross_domain
    - Candidate retrieval
    - LLM reranking
    
    Explain WHY reasoning-first matters: the thinking field is returned 
    to the client, making the agent's reasoning transparent to judges 
    and end users alike.

4b. Retrieval Strategy
    Document the three retrieval paths:
    
    WARM USER: semantic query against items collection using user's 
    top_categories as query text. Category filter removed after discovering 
    Yelp items use specific category names (Food Trucks, Hawaiian) not 
    generic ones (restaurants).
    
    COLD START: three-layer fallback:
      Layer 1: explicit preference extraction from persona_text via LLM
      Layer 2: Nigerian cultural defaults (Lagos popular spots, 
                Trending Naija picks) when nigerian_mode=True
      Layer 3: popularity-based fallback
    
    CROSS-DOMAIN: detect when user platform ≠ target domain, 
    invoke CrossDomainBridge, blend with semantic fallback candidates

4c. LLM Reranking
    From task_b/ranker.py — document the real implementation:
    - Sends top 8 candidates (reduced from 20 after MAX_TOKENS failure)
    - max_tokens=4096
    - Instructs Gemini to return JSON array: {item_id, score, explanation}
    - JSON truncation recovery: rfind("}")  + "]" repair strategy
    - Falls back to heuristic scoring if JSON unparseable

4d. Key Engineering Challenge — Document this real finding:
    "The items collection represents a 0.4% sample of the full Yelp 
     business dataset (327 items from ~150k businesses). For warm users 
     whose reviewed businesses fall outside this sample, history-based 
     collaborative filtering degrades to semantic content-based retrieval. 
     This is a graceful fallback — the user's category profile (e.g. 
     Grocery, Arts & Crafts) still produces semantically relevant 
     candidates even without exact item matches."

4e. Multi-Turn Conversation
    From task_b/conversation.py — document session management:
    in-memory dict keyed by session_id, how history is maintained,
    how preferences are refined across turns.

SECTION 5 — Nigerian Contextualization (0.5 pages)
Extract from shared/nigerian_adapter.py and shared/user_profile.py:

- NIGERIAN_TERMS lexicon from user_profile.py (list the actual terms)
- Three intensity levels: light, medium, full — what each does
- How nigerian_signals are detected in historical reviews
- How the adapter modifies review text (second LLM call)
- How cold-start defaults use Nigerian cultural context
- Note the known issue: second LLM call at medium intensity sometimes 
  truncates output — documented as known limitation

SECTION 6 — Experiments & Results (0.75 pages)

6a. Run the evaluation scripts and extract real numbers:
    python -m eval.run_task_a_eval
    python -m eval.run_task_b_eval
    
    If evaluation hasn't run yet, document the evaluation methodology:
    Task A: ROUGE-1, ROUGE-L, BERTScore-F1 vs held-out reviews, RMSE
    Task B: NDCG@10, Hit Rate@10 on held-out items

6b. Ablation Study 1 — Task A: LLM vs Fallback
    Document what happened before and after fixing the LLM pipeline:
    BEFORE fix: All reviews generated by deterministic template
      "I tried {item} in the {category} category..."
    AFTER fix: LLM generates contextual, user-specific reviews
    This is a natural ablation — the fallback IS the baseline.

6c. Ablation Study 2 — Task B: Category Filter vs No Filter  
    BEFORE: category filter on items query returned 0 results
    AFTER: removing filter and relying on semantic similarity 
           returned 15 relevant candidates
    Lesson: strict categorical filtering hurts recall when category 
    taxonomy doesn't match between query and stored items.

6d. Ablation Study 3 — Ranker token budget
    BEFORE: 30 candidates, 2048 tokens → MAX_TOKENS, JSON parse failure
    AFTER: 8 candidates, 4096 tokens → STOP, successful JSON parse
    Lesson: LLM-as-ranker requires careful budget management. 
    Per-candidate token cost ~70 tokens for structured JSON output.

SECTION 7 — Known Limitations & Future Work (0.5 pages)
Extract from actual observed behavior:

Known Limitations (be honest — judges respect this):
1. Items collection covers only 0.4% of Yelp businesses — warm user 
   collaborative filtering degrades to content-based for most users
2. Nigerian adapter truncation at medium/full intensity — second LLM 
   call sometimes hits token limit mid-sentence
3. Session state is in-memory only — lost on server restart
4. Amazon reviews returned 0 test-split records due to empty reviewText 
   bug in batch insert (defensive fix applied but some records lost)
5. StyleFingerprint fields (rating_std, sentiment, formality) stored in 
   ChromaDB document text rather than metadata — requires regex parsing 
   on each request rather than direct metadata access

Future Work (genuine, not boilerplate):
1. Run full ingestion (not --sample-only) to populate items collection 
   with 150k+ Yelp businesses — this alone would fix warm user retrieval
2. Persist StyleFingerprint fields as explicit ChromaDB metadata fields
3. Fine-tune embedding model on Nigerian review text for better semantic 
   similarity in local context
4. Redis-backed session storage for conversation persistence
5. Streaming API responses to reduce perceived latency (currently 
   10-15 seconds per Task A request, 5-8 seconds per Task B request)
6. User feedback loop: incorporate explicit ratings back into ChromaDB 
   to improve future recommendations

</paper_structure>

<output_format>
For each section produce:

SECTION [N]: [TITLE]
Target length: [X] pages
Core argument: [one sentence — what is this section proving?]

CONTENT:
[Full prose OR detailed bullet points with real numbers and code references]

KEY QUOTE FOR THIS SECTION:
[One punchy sentence that could be the opening or closing of this section]

REAL DATA TO INCLUDE:
[Specific numbers, variable names, file references to pull from codebase]

Do NOT write generic filler. Every sentence must contain a real 
implementation detail, a real number, or a real engineering insight.
If a number isn't available (eval not run yet), say so explicitly 
and provide the methodology instead.
</output_format>

<tone>
- Write like an engineer explaining to another engineer, not a student 
  explaining to a professor
- Use active voice: "We discovered", "The bug manifested as", 
  "This forced us to"
- Be honest about failures — the ranker token budget failure is more 
  interesting than a clean success
- Specific > general: "the rfind('}') truncation recovery strategy" 
  is better than "we added error handling"
- One insight per paragraph — don't pack multiple ideas together
</tone>