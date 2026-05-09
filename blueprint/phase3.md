PHASE 3 PROMPT — Task B: Recommendation Agent Core
<role>
You are a Senior AI Engineer specializing in agentic RAG systems, 
conversational recommendation, and LLM reasoning loops. You design 
systems that reason before they retrieve, not the other way around.
</role>

<project_context>
This is Task B of the DSN x BCT hackathon. The recommendation agent must:
1. Accept a UserPersona input (may be cold-start with zero history)
2. Run a reasoning loop BEFORE retrieval (think → plan → retrieve → rank → respond)
3. Return a ranked list of recommendations with explanations
4. Handle multi-turn conversation (session_id based state)

Scoring breakdown (100 pts total):
  30pts — Ranking Quality (NDCG@10, Hit Rate) — needs good retrieval + reranking
  25pts — Cold-Start & Cross-Domain — needs fallback strategies
  20pts — Contextual Relevance (human eval) — needs good explanations
  15pts — Solution Paper — architecture clarity
  10pts — Code quality

Agent reasoning loop (Chain-of-Thought before retrieval):
  Step 1 — QueryAnalyzer: understand what user actually wants 
    (explicit preferences, implicit signals, constraints)
  Step 2 — StrategyPlanner: decide retrieval strategy
    (collaborative if warm user, content-based if cold, hybrid if cross-domain)
  Step 3 — MultiSourceRetriever: query ChromaDB with appropriate strategy
  Step 4 — LLMRanker: Claude re-ranks candidates with contextual reasoning
  Step 5 — ResponseFormatter: structured response with explanations

Cross-domain: if user has Goodreads data, infer movie/food preferences.
Cold-start: use demographic signals, explicit preferences, Nigerian cultural defaults.
Multi-turn: maintain conversation history in memory (dict keyed by session_id).
</project_context>

<existing_code>
C:\Users\DanielsFega\Hackathons\bcthack\shared
C:\Users\DanielsFega\Hackathons\bcthack\task_b
</existing_code>

<task>
Implement these files completely:

1. task_b/agent.py — RecommendationAgent
   - Core reasoning loop as described above
   - async recommend(request: RecommendRequest) → RecommendResponse
   - async chat(request: ChatRequest) → ChatResponse (multi-turn)
   - Internal method _build_reasoning_prompt() that generates a step-by-step 
     thinking chain before retrieval queries are formulated

2. task_b/retriever.py — MultiSourceRetriever
   - query_by_user_history(user_id, category, top_k=20) → list[Item]
   - query_by_content(item_attributes, top_k=20) → list[Item]
   - query_cross_domain(source_domain, target_domain, user_id) → list[Item]
   - Each method queries ChromaDB and returns candidates with similarity scores

3. task_b/cold_start.py — ColdStartHandler
   - detect_cold_start(user_profile) → bool
   - handle(user_profile, request_context) → list[Item]
   - Strategies: 
     a) Explicit preference extraction from persona text via Claude
     b) Nigerian cultural defaults (popular local items by category)
     c) Popularity-based fallback from dataset statistics
     d) Hybrid: combine all three with weighted scoring

4. task_b/cross_domain.py — CrossDomainBridge
   - infer_cross_domain_preferences(source_reviews, target_domain) → PreferenceMap
   - Example: user loves "dark thriller novels" on Goodreads → 
     infer they'd like intense Nigerian crime series, spicy foods, bold flavors
   - Uses Claude to reason about the preference transfer
   - PreferenceMap: {attribute: weight} dict

5. task_b/conversation.py — ConversationManager
   - In-memory session store (dict, keyed by session_id)
   - add_turn(session_id, user_msg, assistant_msg, context)
   - get_history(session_id) → list[Turn]
   - extract_refined_preferences(session_id) → PreferenceMap
     (uses Claude to summarize what the conversation revealed about user)
   - clear_session(session_id)

6. task_b/ranker.py — LLMRanker
   - rerank(candidates: list[Item], user_profile, query_context) → list[RankedItem]
   - Builds a prompt with all candidates + user profile
   - Claude scores each candidate 0–10 with reasoning
   - Returns sorted list with explanation strings
   - RankedItem: item + score + explanation + confidence

7. task_b/main.py — complete FastAPI app
   - POST /recommend — single-shot recommendation
   - POST /recommend/chat — multi-turn conversational recommendation
   - GET /recommend/session/{session_id} — get conversation history
   - DELETE /recommend/session/{session_id} — clear session
   - GET /health

<constraints>
- The reasoning loop in agent.py must produce a "thinking" field in the response 
  (so judges can see the agent reasoned before retrieving)
- All retrieval is async
- RankedItem must include an "explanation" field — this is what drives the 
  contextual relevance score (human eval)
- Nigerian mode: cold-start defaults should reference Nigerian contexts 
  (Jollof rice, Nollywood, Lagos restaurants, etc.)
- Session state is in-memory (acceptable for hackathon; note in README)
</constraints>

<output_format>
Full files, path headers, complete type hints, docstrings. No truncation.
</output_format>