<role>
You are a technical writer and ML engineer who has won multiple AI 
hackathons. You write solution papers that read like engineering 
postmortems — precise, honest, full of insight. Never pad with fluff.
</role>

<task>
Generate a complete content brief for a 4-6 page solution paper 
for TASK B (Recommendation) of the DSN x BCT LLM Agent Hackathon.

The paper covers ONLY Task B. It must read like a senior engineer 
wrote it — deliberate decisions, real obstacles, genuine insights.
</task>

<known_facts_from_implementation>
ARCHITECTURE:
- Task B service: port 8002
- ChromaDB: users(394), items(499), reviews(5212)
- Three retrieval strategies: warm_history_content_hybrid, 
  cold_start_hybrid, hybrid_cross_domain
- Endpoints: POST /recommend, POST /recommend/chat, 
  GET /recommend/session/{id}, DELETE /recommend/session/{id}

CONFIRMED WORKING FEATURES:
- Warm user detection: review_count >= 3 from ChromaDB metadata
  User yelp__BcWyKQL16ndpBdggh2kNA: 65 reviews → warm
- Cold start: 3-layer fallback producing real ChromaDB items
  (Treme Coffeehouse, Say Cheese, Blueplate from cold user test)
- Cross-domain: amazon → books, goodreads → food both fire correctly
- Multi-turn chat: session state confirmed across 3 turns
  Constraints accumulate: Turn 3 respects Turn 1+2 constraints
  Category pivot works: restaurants → bars in single session
- Nigerian mode in chat: natural tone confirmed
  "That one na proper restaurant, o" 
  "Ehen! Say Cheese — this one is getting serious buzz"
- Session storage: in-memory dict, confirmed working for warm users
  Cold user session storage was broken — fixed in latest update

REAL BUGS AND ENGINEERING FINDINGS:
1. ChromaDB not queried at all initially — same dotenv issue as Task A
2. Every user treated as cold start — agent checked request.history
   (always []) instead of ChromaDB review_count
3. Category filter on items query returned 0 results:
   Query used "restaurants" but items stored as "Food Trucks", 
   "Hawaiian", "Bars" — taxonomy mismatch
   Fix: removed category filter, rely on semantic similarity only
4. Item resolution failure: reviews store raw Yelp business IDs
   (e.g. "L3V21nAe-CicW2bvtNWa0g") but items collection stores
   prefixed IDs ("yelp_L3V21nAe-CicW2bvtNWa0g"). 
   Only 1 of 15 history items resolved (Octopus Falafel Truck).
   Root cause: items collection is 0.4% sample of full Yelp dataset
   (327 items from ~150k businesses). Most reviewed businesses
   simply not in the sample.
   Fix: switched warm user retrieval from history-lookup to 
   semantic query using top_categories as query text.
5. LLM ranker JSON truncation:
   BEFORE: 30 candidates, 2048 tokens → MAX_TOKENS, JSON parse error
   "Unterminated string starting at: line 6 column 20"
   AFTER: 8 candidates, 4096 tokens → STOP, successful JSON parse
   Added rfind("}") truncation recovery as additional safety net
6. Rate limiting: 20 req/day Gemini free tier
   Each recommend/chat turn makes 3-4 LLM calls:
   ranker + nigerian adapter × N items + conversation summarization
   Fix: Groq (llama-3.3-70b) fallback on 429

MULTI-TURN CHAT CONFIRMED RESULTS (Sequence 1):
Turn 1: "I want somewhere good to eat tonight in Lagos"
  → Treme Coffeehouse (9.5), Blueplate (8.5), Say Cheese (8.0)
Turn 2: "Something spicy and under 3000 naira, on the island"
  → constraints accumulated, Nigerian tone maintained
Turn 3: "What about pepper soup or suya specifically?"
  → further refinement

SESSION ENDPOINT CONFIRMED:
chat_warm_001 shows all 3 turns with correct context:
  Turn 1: constraints=[]
  Turn 2: constraints=["casual","affordable","group-friendly"]  
  Turn 3: constraints=["casual","group-friendly"], category="bars"

SCORING RUBRIC (from brief):
  30pts — Ranking Quality (NDCG@10, Hit Rate@10)
  25pts — Cold-Start & Cross-Domain handling
  20pts — Contextual Relevance (human eval of explanations)
  15pts — Solution Paper
  10pts — Code Reproducibility
</known_facts_from_implementation>

<codebase_to_scan>
Read these files for exact implementation details:
task_b/agent.py          — reasoning loop, warm/cold detection,
                           strategy selection, thinking[] generation
task_b/retriever.py      — all three retrieval paths
task_b/cold_start.py     — three-layer cold start logic
task_b/cross_domain.py   — cross-domain bridge implementation
task_b/conversation.py   — session management, preference refinement
task_b/ranker.py         — LLM reranking, JSON recovery
task_b/schemas.py        — RankedItem, thinking field structure
shared/prompts.py        — TASK_B_RERANK_SYSTEM, TASK_B_RERANK_USER
shared/nigerian_adapter.py — adapt_recommendation_explanation()
</codebase_to_scan>

<paper_structure>

SECTION 1 — Problem Framing (0.5 pages)
Core argument: Recommendation is a reasoning problem, not a retrieval 
problem. Most systems retrieve then rank. We reason then retrieve.

Write:
- What Task B asks for: ranked, personalized recommendations that 
  handle cold-start, cross-domain, and multi-turn scenarios
- The key design decision: reasoning loop BEFORE retrieval
  The agent must decide WHAT to retrieve before retrieving it
- The thinking[] field: why making reasoning transparent is both 
  an engineering and evaluation advantage

SECTION 2 — System Architecture (0.75 pages)
Include ASCII diagram. Document:
- Three endpoints and their purposes
- The reasoning loop sequence: interpret → detect → plan → 
  retrieve → rerank → respond
- Strategy taxonomy: warm_history_content_hybrid, cold_start_hybrid,
  hybrid_cross_domain
- Why ChromaDB semantic search over keyword search for this use case
- The Groq fallback architecture for rate limit resilience

SECTION 3 — The Reasoning-First Agent Loop (1 page)

3a. Query interpretation: extract exact thinking[] generation from agent.py
3b. Warm/cold detection: review_count >= 3 threshold, why this number
    Document the bug: initially checked request.history (always [])
    Fix: check ChromaDB metadata review_count directly
3c. Strategy selection logic — extract from agent.py
3d. The thinking[] field design: why return it to the client
    "A model score reflects what your machine did. A solution paper 
     reveals what you understood." — same principle applies to 
     the thinking field: it reveals what the agent understood.

SECTION 4 — Retrieval Strategies (1 page)

4a. WARM USER — semantic retrieval using top_categories
    Why we abandoned history-item lookup: the 0.4% sample problem
    "327 items from ~150k Yelp businesses means most reviewed items 
     simply don't exist in our index. This forced a strategy shift 
     from collaborative filtering to content-based retrieval using 
     the user's category preferences as the semantic query."
    
4b. COLD START — three-layer fallback
    Extract the exact layers from cold_start.py:
    Layer 1: LLM extracts preferences from persona_text
    Layer 2: Nigerian defaults when nigerian_mode=True
    Layer 3: Popularity-based fallback
    
    Show cold start working: cold_user_lagos_001 with
    persona_text="I enjoy local restaurants, prefer spicy food"
    → Treme Coffeehouse (4.5★), Blueplate (4.0★), Say Cheese (4.0★)

4c. CROSS-DOMAIN — preference bridge
    Extract from cross_domain.py: how source preferences map to target
    amazon (Electronics reviews) → books recommendations
    goodreads (fantasy/sci-fi) → food/restaurant recommendations

4d. Category taxonomy mismatch bug:
    Query: "restaurants" → ChromaDB filter → 0 results
    Stored: "Food Trucks", "Hawaiian", "Bars", "Dog Parks"
    Fix: remove category filter, use semantic similarity
    Lesson: never trust taxonomy alignment between query and index

SECTION 5 — LLM Reranking & Nigerian Contextualization (0.75 pages)

5a. Ranker architecture: extract from ranker.py
    - 8 candidates (not 20 — explain why)
    - 4096 token budget
    - JSON schema: {item_id, score (0-10), explanation (max 50 words)}
    - _safe_parse_json(): the rfind("}") recovery strategy
    
5b. The token budget ablation:
    BEFORE: 30 candidates, 2048 tokens 
    Error: "Unterminated string at line 6 column 20"
    AFTER: 8 candidates, 4096 tokens
    Result: finish_reason=STOP, clean JSON parse
    Lesson: per-candidate JSON output costs ~70 tokens. 
    Budget: (4096 - prompt_overhead) / 70 = ~45 candidates max.
    We chose 8 for safety margin.

5c. Nigerian adapter for explanations:
    adapt_recommendation_explanation() — second LLM call
    Confirmed outputs from testing:
    "That one na proper restaurant, o. They've got a fantastic 
     average rating of 4.5"
    "Ehen! Say Cheese — this one is getting serious buzz, my friend!"

SECTION 6 — Multi-Turn Conversation (0.5 pages)

6a. Session architecture: in-memory dict keyed by session_id
    ConversationManager.add_turn() saves after every response
6b. Constraint accumulation: confirmed across 3 turns
    Turn 1: [] → Turn 2: ["casual","affordable"] → 
    Turn 3: ["casual","group-friendly"] + category pivot to "bars"
6c. Preference refinement: LLM summarizes conversation history
    Rate limit causes this to fail gracefully (confirmed in logs)
6d. Known limitation: cold user session not saved initially
    Root cause: add_turn() called inside warm branch only, not 
    after all branches. Fixed: moved to post-response always.

SECTION 7 — Experiments & Ablations (0.75 pages)

7a. Evaluation methodology:
    NDCG@10: measures ranking quality of top-10 recommendations
    Hit Rate@10: fraction of held-out items appearing in top-10
    Test split: last 20% of each user's reviews (706 total)

7b. Ablation 1 — Cold start detection bug
    BEFORE: 394 users all treated as cold start (review_count=0)
    AFTER: correct warm/cold split based on ChromaDB metadata
    Impact: warm users now get semantic retrieval using their 
    actual category history instead of popularity fallback

7b. Ablation 2 — Category filter removal
    BEFORE: WHERE category="restaurants" → 0 candidates
    AFTER: semantic only → 15 candidates
    Lesson: taxonomy mismatch kills recall before ranking can help

7c. Ablation 3 — Ranker token budget
    BEFORE: 30 candidates, 2048 tokens → JSON truncation, fallback
    AFTER: 8 candidates, 4096 tokens → clean JSON, LLM explanations
    Measurement: per-candidate cost ~70 tokens for structured output

7d. Rate limit as system design constraint:
    3-4 LLM calls per recommend/chat request × 9 turns = 27-36 calls
    Exceeds 20/day free tier in a single test session
    Fix: Groq fallback — separate quota pool, llama-3.3-70b-versatile
    Production lesson: multi-provider routing is a reliability 
    requirement, not an optimization

SECTION 8 — Known Limitations & Future Work (0.5 pages)
Limitations:
1. Items collection: 499 items is too small for meaningful NDCG
   (most warm user reviewed items not in index)
2. Session state lost on restart (in-memory only)
3. Explanation truncation when Nigerian adapter hits rate limit
4. Thinking[] array is template-heavy — real reasoning depth 
   limited by prompt design, not model capability
5. Cross-domain inference is heuristic — no learned transfer function

Future Work:
1. Full ingestion: 150k+ Yelp items fixes warm user retrieval
2. Learned cross-domain embeddings
3. Redis-backed persistent sessions
4. Streaming recommendations (show items as ranked, not batch)
5. NDCG optimization: rerank using user's historical rating pattern
   (high-rating users should see higher-quality items first)

</paper_structure>

<output_format>
For each section output:

SECTION [N]: [TITLE]
Target length: [X] pages
Core argument: [one sentence]

PROSE:
[Write the actual prose as it would appear in the paper.
Active voice. Specific. Real variable names and numbers.]

KEY INSIGHT LINE:
[One sentence capturing the most important idea]
</output_format>

<tone>
Engineer to engineer. Active voice. Honest about failures.
Real numbers. Never say "robust" or "seamless" or "leverages".
</tone>