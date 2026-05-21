# Task B Solution Paper Brief

SECTION 1: Problem Framing
Target length: 0.5 pages
Core argument: Task B is a reasoning problem because the agent has to decide what evidence matters before retrieval begins.

PROSE:
Task B asks for ranked, personalized recommendations under three conditions that usually break simple recommenders: cold start, cross-domain transfer, and multi-turn conversation. In engineering terms, that means the system cannot just take a query, run nearest-neighbor search, and call the top results personalized. It has to infer whether the user is warm or cold, whether the request implies a domain shift, whether prior chat turns contain constraints that are not present in the latest message, and whether the current retrieval plan is likely to return useful candidates at all.

That requirement is why the Task B service in `task_b/agent.py` is organized as a reasoning-first loop. The agent builds `thinking` before it finalizes retrieval. `_build_reasoning_prompt()` generates explicit reasoning strings such as `Think: interpret the query as ...`, `Think: user has X stored interactions ...`, and `Plan: explicit persona preferences are ...`. This happens before ranking. The practical point is simple: retrieval quality depends on asking the right question of the index. If the system misclassifies a warm user as cold, or treats a cross-domain request as in-domain, no reranker can recover the lost recall.

Returning `thinking` to the client is not just a demo flourish. It is useful for engineering and evaluation. When the agent says it treated a user as `cold start`, or that it added semantic fallback because `history items could not be resolved`, that gives a direct trace of what the planner believed. A numeric score alone cannot tell you why a candidate surfaced. In a hackathon setting, this matters twice: it helps diagnose ranking failures quickly, and it gives evaluators evidence that the system is actually reasoning about context instead of hiding everything behind an opaque top-k list.

The main design decision was to make retrieval strategy a derived decision rather than a fixed pipeline step. That is the difference between a system that always queries the same way and a system that can survive mismatched taxonomies, sparse item indices, and chat sessions where the user's third turn changes the category entirely.

KEY INSIGHT LINE:
Task B works when the agent decides what to retrieve before retrieval, not after bad candidates are already in the ranking pool.

SECTION 2: System Architecture
Target length: 0.75 pages
Core argument: The Task B architecture is a compact reasoning loop wrapped around ChromaDB retrieval, LLM reranking, and session memory.

PROSE:
Task B runs as a dedicated service on port `8002`. It exposes four endpoint behaviors through its schemas and service flow: `POST /recommend` for single-shot recommendation, `POST /recommend/chat` for multi-turn conversational recommendation, `GET /recommend/session/{id}` for recovering stored chat history, and `DELETE /recommend/session/{id}` for clearing session state. The response models in `task_b/schemas.py` make the contract explicit: `RecommendResponse` returns `recommendations`, `thinking`, `strategy`, and optional `session_id`; `ChatResponse` adds `assistant_message` and `refined_preferences`.

The execution path in `task_b/agent.py` is consistent across both single-turn and chat flows:

```text
User query / chat turn
        |
        v
Interpret request + load conversation history
        |
        v
Fetch Chroma user -> detect warm/cold -> pick strategy
        |
        v
Retrieve candidates from one or more paths
        |
        v
LLM rerank + explanation generation
        |
        v
Optional Nigerian adaptation of explanations
        |
        v
Persist session turn and return response
```

The strategy taxonomy is implemented in `_plan_strategy()` and has three named modes: `warm_history_content_hybrid`, `cold_start_hybrid`, and `hybrid_cross_domain`. The names are not cosmetic. They are returned to the client and therefore become part of the system's debuggability. The warm path starts from user evidence already in ChromaDB. The cold path tries live retrieval first and then supplements with cold-start defaults when the live candidate pool is too small. The cross-domain path layers inferred preferences from one domain into retrieval for another domain.

ChromaDB is a better fit here than keyword search because the data is semantically messy. Item categories include values like `Food Trucks`, `Hawaiian`, and `Bars`, while the incoming query may ask for `restaurants`. Semantic search can bridge that mismatch; exact category filtering cannot. That same semantic layer also makes cross-domain retrieval possible, because the system can search for item meaning rather than exact lexical overlap.

The rate-limit resilience story is more mixed. The blueprint and debugging notes describe Groq as an intended fallback on Gemini 429s. The current `shared/llm_client.py` that Task B actually uses exposes Gemini retry logic, parsed retry delays from 429 error messages, and a process-wide `FREE_TIER_MODE` throttle that spaces calls by three seconds. It does not expose a dedicated provider router in the verified code path. The practical effect is that Task B today relies on bounded Gemini retries plus deterministic fallbacks in downstream components when the LLM path fails.

KEY INSIGHT LINE:
The architecture is small, but every major response field maps cleanly to one stage in the reasoning loop, which made the debugging effort tractable.

SECTION 3: The Reasoning-First Agent Loop
Target length: 1 page
Core argument: The main contribution of Task B is not a novel retriever, but an agent loop that turns user state into an explicit retrieval plan.

PROSE:
The reasoning loop begins in `RecommendationAgent._recommend_internal()` inside `task_b/agent.py`. The agent first loads `conversation_history` from `ConversationManager` if a `session_id` is present, then asks `extract_refined_preferences()` for a compact preference map inferred from prior turns. After that it fetches the user's Chroma summary with `self.vector_store.get_by_id("users", request.user_persona.user_id)`, derives `review_count` from metadata, and computes `is_warm` through `_is_warm_user()`.

The pre-retrieval reasoning trace comes from `_build_reasoning_prompt()`. It emits five lines in the current code:

```text
Think: interpret the query as '{query}' with target category '{...}'.
Think: user has {review_count} stored interactions, treated as warm or cold start.
Plan: explicit persona preferences are {...} and conversation refinements are {...}.
Plan: constraints considered before retrieval are {...} and attributes {...}.
Plan: top categories from history are {...}.
```

That list is deliberately simple. It is template-heavy, but it exposes the exact variables driving the next step. Because it is returned to the client as `thinking`, the trace becomes part of both system observability and the product output.

Warm/cold detection is where one of the most important bugs lived. The confirmed fix is in `_is_warm_user()`, which checks `review_count` directly from ChromaDB metadata and returns `True` for users with at least three stored reviews. The threshold is small, but sensible for this dataset size. Fewer than three reviews is usually not enough evidence to trust category history or interaction patterns. The earlier broken version inspected the request payload history, which was often empty even for users who had many interactions in ChromaDB. That bug forced essentially every user into the cold-start path and erased the benefit of the precomputed user store.

Strategy selection is straightforward but important. `_plan_strategy()` returns `cold_start_hybrid` if `is_warm` is false. It returns `hybrid_cross_domain` if cross-domain mode is enabled, the request has a `target_domain`, and the source platform does not match that target. Otherwise it returns `warm_history_content_hybrid`. Those branches encode the system's operating assumptions explicitly instead of hiding them inside retriever heuristics.

The `thinking` field is valuable precisely because the code is not doing deep chain-of-thought reasoning. It is doing structured planning. That is the right trade-off here. The agent exposes just enough internal state to show what it understood: the user warmth classification, the active constraints, the resolved categories, and whether semantic fallback or cross-domain inference were activated.

KEY INSIGHT LINE:
The best part of the agent loop is not that it is complicated; it is that every strategic choice is explicit enough to inspect when the outputs look wrong.

SECTION 4: Retrieval Strategies
Target length: 1 page
Core argument: Retrieval quality improved only after the system stopped assuming the dataset index was complete and the taxonomy was aligned.

PROSE:
The warm-user path starts in `task_b/retriever.py` with `query_by_user_history()`, which calls `retrieve_user_history_items()`. That function queries the `reviews` collection for a user's historical items, then tries to resolve each raw `item_id` back into the `items` collection by testing multiple candidate forms, including raw IDs and prefixed IDs like `yelp_{raw_item_id}`. This logic was necessary because reviews stored raw Yelp business IDs while the `items` collection stored prefixed IDs. The engineering lesson was more severe than a prefix mismatch, though. Even after the prefix fix, most reviewed Yelp businesses still did not exist in the sampled `items` collection at all.

That gap forced a strategy shift. The sample index contains 327 Yelp items out of roughly 150k businesses in the full dataset. In practice that means most history lookups cannot be resolved to a real item document. `RecommendationAgent._retrieve_candidates()` measures this with `unresolved_ratio = 1 - (len(resolved_history) / max(len(history_candidates), 1))`. If more than 50 percent of history candidates are unresolved, the agent adds semantic item search by calling `retrieve_semantic_candidates()` with a query built from the current request and the user's `preferred_categories`. This is the real warm-user strategy now: use historical categories as semantic evidence, not as hard item identifiers.

The cold-start path is implemented in `task_b/cold_start.py` as a three-layer fallback. Layer 1 is explicit preference extraction through `TASK_B_COLD_START_SYSTEM` and `TASK_B_COLD_START_USER`, where the LLM turns `persona_text`, existing preferences, and request context into a weighted map. Layer 2 applies Nigerian defaults through `NigerianContextAdapter.get_cultural_defaults()` when `nigerian_mode=True`, yielding category-specific defaults like `Jollof rice`, `Suya spot`, `Buka`, and `Pepper soup`. Layer 3 adds popularity-based fallbacks from `POPULARITY_FALLBACKS`, such as `Popular Jollof Kitchen` and `Lagos Rooftop Lounge`. The handler merges these layers into weighted `Item` objects and sorts by `similarity_score`. The confirmed cold-start behavior surfaced real ChromaDB-backed recommendations like `Treme Coffeehouse`, `Blueplate`, and `Say Cheese` before fallback supplementation filled any remaining gaps.

The cross-domain path lives in `task_b/cross_domain.py`. `CrossDomainBridge.infer_cross_domain_preferences()` first tries to ask the LLM for a JSON preference map from source reviews and a target domain. If that fails, it falls back to heuristics and `DOMAIN_BRIDGES`, which encode mappings such as `goodreads:food -> {"bold flavors": 0.76, "spicy dishes": 0.7}` and `goodreads:movies -> {"intense storytelling": 0.8, "nollywood crime drama": 0.72}`. In the agent, those inferred preferences are attached to candidate metadata and slightly boost `similarity_score` by `sum(inferred_preferences.values()) * 0.02`, capped at `0.99`.

The taxonomy mismatch bug explains why semantic retrieval was necessary even outside cross-domain scenarios. In `_retrieve_candidates_sync()`, the retriever first tries a filtered query with `where={"category": {"$eq": category}}`. This is exactly the kind of filter that fails when the request says `restaurants` but the index stores `Food Trucks`, `Hawaiian`, or `Bars`. The fallback branch reruns the same semantic query without the category constraint. That is the correct default for this dataset. Keyword or exact-taxonomy filtering cut recall before ranking ever had a chance to help.

KEY INSIGHT LINE:
The retrieval strategy became useful only after we accepted that the index was sparse and the taxonomy was unreliable.

SECTION 5: LLM Reranking & Nigerian Contextualization
Target length: 0.75 pages
Core argument: The reranker improved recommendation quality, but only after the candidate count and token budget were brought in line with the JSON output format.

PROSE:
The ranking layer is implemented in `task_b/ranker.py` by `LLMRanker`. Its job is not to retrieve candidates. It takes already retrieved `Item` objects, asks the LLM to rerank them, and returns a list of `RankedItem` objects with `score`, `confidence`, and `explanation`. The current code deliberately caps LLM input to `llm_candidates = candidates[:8]` and uses `max_tokens=4096`. The prompt extends `TASK_B_RERANK_SYSTEM` with extra instructions to explain why each item fits this specific user rather than returning generic preference language.

The output contract is strict. The system prompt requires a JSON array of objects with `item_id`, `score`, `confidence`, and `explanation`. `_parse_ranked_response()` then maps those rows back onto the original candidate set. The design is narrow on purpose: machine-readable JSON is easier to salvage and easier to evaluate than free-form explanation text.

The token-budget ablation was one of the clearest wins in Task B. Earlier runs attempted around 30 candidates with a 2048-token cap, which caused `MAX_TOKENS` endings and broken JSON such as `Unterminated string starting at: line 6 column 20`. The current code reduces the candidate count to 8 and increases the token budget to 4096. That is not arbitrary. Structured JSON with explanations is expensive. If each candidate costs around 70 tokens once item identifiers, scores, confidence, and explanation text are included, large candidate sets quickly exhaust a practical budget after prompt overhead. Choosing 8 candidates gave enough safety margin that the model could finish with clean JSON instead of half-written objects.

The recovery logic matters because truncation still happens in the wild. `_extract_json_payload()` strips markdown fences, tries to parse the full array, and if that fails, scans the text for complete JSON objects inside the array. For each balanced object it can parse successfully, it salvages that object and rebuilds a smaller valid array. The code logs how many complete rows were recovered. This is a better failure mode than throwing away the entire LLM response because the last explanation was cut off.

Nigerian contextualization for Task B explanations is implemented as a second pass through `NigerianContextAdapter.adapt_recommendation_explanation()`. For each ranked item, `_parse_ranked_response()` rewrites the explanation if `nigerian_mode=True`, and `adapt_category()` can also localize the category label. The confirmed outputs from testing, such as `That one na proper restaurant, o` and `Ehen! Say Cheese — this one is getting serious buzz`, show that the second-stage rewrite can make explanations feel more locally situated without changing the ranking logic itself.

KEY INSIGHT LINE:
The reranker became reliable only when we treated structured output as a token-budgeting problem, not just a prompting problem.

SECTION 6: Multi-Turn Conversation
Target length: 0.5 pages
Core argument: The conversation layer is intentionally simple, but it changes Task B from a one-shot recommender into a stateful planner.

PROSE:
Session state is managed by `ConversationManager` in `task_b/conversation.py`. The storage model is an in-memory dictionary, `self._sessions: dict[str, list[Turn]]`, keyed by `session_id`. `add_turn()` appends a `Turn` containing `user_message`, `assistant_message`, and a structured `context` dictionary. `get_history()` returns the accumulated turns, and `clear_session()` drops the session entirely.

The chat flow in `RecommendationAgent.chat()` relies on that state in two places. First, before retrieval, it calls `extract_refined_preferences()` so prior turns can be summarized into a compact preference map. That method tries an LLM summary first, then falls back to a deterministic count-based map where each repeated constraint adds `0.3` and each category mention adds `0.4`, capped at `1.0`. Second, after the response is built, the agent always saves the turn through `await self.conversation.add_turn(...)`. That last placement matters because it fixes the earlier bug where cold-user chat branches could return successfully but never persist the session turn.

The multi-turn behavior confirmed in testing shows why even this lightweight memory layer matters. Constraints accumulate across turns, and category pivots are preserved within the same session. A conversation can start with restaurants, then narrow by affordability and group-friendliness, then pivot to bars without losing the prior context. The session endpoint reflects that context as stored `Turn.context` objects rather than as inferred prose.

The limitation is durability. Because sessions live only in process memory, a service restart drops everything. That is acceptable for a hackathon prototype and useful for debugging, but not enough for production conversation continuity.

KEY INSIGHT LINE:
The conversation layer does not make the model smarter by itself; it makes prior user constraints impossible to ignore.

SECTION 7: Experiments & Ablations
Target length: 0.75 pages
Core argument: The strongest improvements in Task B came from fixing false assumptions about user state, taxonomy alignment, and LLM output budgets.

PROSE:
The evaluation plan for Task B follows the hackathon rubric: ranking quality is measured with NDCG@10 and Hit Rate@10 against held-out user interactions, using the same deterministic last-20-percent split pattern that yields 706 test reviews across the sampled platforms. NDCG@10 measures whether the most relevant recommendations are placed near the top of the ranked list. Hit Rate@10 measures whether at least one held-out item appears in the top 10. These metrics reflect the scoring rubric directly, but the debugging journey also produced three clear ablations that explain where the quality gains came from.

The first ablation is warm/cold detection. Before the fix, the agent relied on request history and effectively treated nearly all users as cold because many requests arrived with empty `history`. After the fix, `_is_warm_user()` checks `review_count` in ChromaDB metadata and treats users with at least three stored interactions as warm. That changed the strategy mix immediately. Warm users could use their actual stored behavior, while only genuinely sparse users were routed into cold-start fallback logic.

The second ablation is category filtering versus semantic-only retrieval. Before the change, exact category filtering such as `WHERE category="restaurants"` returned zero candidates because the indexed categories did not match the query vocabulary. After the change, the retriever falls back to semantic query without the category constraint, which restores recall. This is one of those bugs that looks like a ranking issue from the outside but is actually a recall collapse caused by taxonomy mismatch.

The third ablation is reranker token budget. Before the change, large candidate pools and a small token cap caused JSON truncation, parse errors, and fallback ranking behavior. After the change to 8 LLM candidates and 4096 output tokens, the ranker started finishing with usable JSON and real explanations. That meant the system could benefit from the LLM's comparative judgment instead of falling back to similarity-based heuristic ranking.

Rate limiting belongs in the ablation story because each `/recommend/chat` turn compounds LLM usage. A single conversational turn can invoke ranking, optional Nigerian rewriting for explanations, and conversation summarization. Across multiple turns, that easily exceeds the Gemini free-tier quota. The current code handles this with parsed retry delays, one final retry after a 429, and shared three-second throttling in `FREE_TIER_MODE`. The broader lesson remains the same as in the debugging notes: multi-provider routing is not a luxury for recommendation agents that chain several LLM-assisted stages.

KEY INSIGHT LINE:
The biggest improvements came from fixing recall and control flow, not from making the prompts more elaborate.

SECTION 8: Known Limitations & Future Work
Target length: 0.5 pages
Core argument: The current Task B system demonstrates the right planning architecture, but several data and infrastructure shortcuts still constrain ranking quality.

PROSE:
The first limitation is dataset coverage. The `items` collection contains only 499 items overall, and only 327 sampled Yelp items, which is too small for meaningful warm-user recommendation when most reviewed businesses never enter the index. This is why the system had to abandon direct history-item lookup in favor of semantic category retrieval. The second limitation is session durability. `ConversationManager` stores turns in an in-memory dictionary, so every process restart loses state. The third limitation is that Nigerian explanation adaptation introduces an extra LLM call, which means explanation quality can still degrade or fall back when quotas are exhausted.

The fourth limitation is that `thinking` is useful but template-heavy. It exposes the planner's state cleanly, but it does not yet show deeper reasoning about trade-offs between constraints. The fifth limitation is that cross-domain inference remains heuristic. `DOMAIN_BRIDGES` and a lightly constrained LLM preference map can produce useful bridges, but there is no learned transfer function across domains.

There is also migration debt visible in the code. `task_b/cross_domain.py` still imports `AnthropicLLMClient`, which is currently just an alias to `GeminiLLMClient` in `shared/llm_client.py`, and it still checks `ANTHROPIC_API_KEY` in `_get_llm_client()`. The file docstrings in `task_b/ranker.py` and `shared/prompts.py` also still refer to Claude. These are not catastrophic bugs, but they are signs that the provider migration is incomplete in parts of the Task B stack.

The future-work path is clear. First, ingest the full Yelp item set so warm-user retrieval can use real item coverage instead of semantic approximation. Second, replace in-memory sessions with Redis-backed persistence. Third, move from heuristic domain bridges to learned cross-domain embeddings or a trained transfer model. Fourth, support streaming recommendations so the agent can reveal strong candidates before the full rerank completes. Fifth, incorporate historical rating behavior into reranking so users with different generosity profiles see different score thresholds near the top of the list.

KEY INSIGHT LINE:
Task B proved the planning pattern, but its next gains depend more on better data coverage and infrastructure than on adding another prompt.
