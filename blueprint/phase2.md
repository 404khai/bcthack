PHASE 2 PROMPT — Task A: User Modeling Agent
<role>
You are a Senior ML Engineer with deep expertise in LLM prompting, behavioral 
modeling, and NLP evaluation. You build systems that accurately simulate human 
writing style and rating behavior.
</role>

<project_context>
This is Task A of the DSN x BCT hackathon submission. The service must:
1. Accept a UserPersona (user_id, review_history[], preferences{}) + ItemDetails 
   (item_id, name, category, attributes{}) as input.
2. Return a GeneratedReview (rating: float 1–5, review_text: str, 
   confidence: float, style_notes: str).

The agent pipeline:
  Step 1 — PersonaBuilder: extract style fingerprint from user's review history
    → avg_rating, rating_variance, vocabulary_richness, sentiment_distribution,
      common_phrases[], review_length_avg, formality_score, nigerian_signals[]
  Step 2 — ContextRetriever: fetch 5 most similar past reviews from ChromaDB 
    (similarity by item category + user_id filter)
  Step 3 — ReviewGenerator: Claude prompt using persona + context → review text
  Step 4 — RatingPredictor: Claude prompt or regression → star rating (1–5)
  Step 5 — NigerianAdapter: if nigerian_mode=True, inject local references/tone

Scoring dimensions:
  - Review Text Quality: ROUGE-L and BERTScore vs held-out real reviews
  - Rating Accuracy: RMSE vs actual ratings
  - Behavioural Fidelity: human eval (judge reads and scores authenticity)
  - Extra marks: Nigerian contextualization
</project_context>

<existing_code>
C:\Users\DanielsFega\Hackathons\bcthack\shared
C:\Users\DanielsFega\Hackathons\bcthack\task_a
</existing_code>

<task>
Implement the following files in full:

1. shared/user_profile.py
   - UserProfile dataclass: user_id, platform, review_history (list of 
     ReviewRecord), style_fingerprint (StyleFingerprint dataclass)
   - StyleFingerprint: avg_rating, rating_std, avg_review_length, 
     vocabulary_size, top_phrases (list[str]), sentiment_profile (dict), 
     formality_score (0–1), nigerian_signals (list[str])
   - build_style_fingerprint(review_history) → StyleFingerprint function

2. task_a/persona_builder.py
   - PersonaBuilder class
   - build(user_id, review_history) → StyleFingerprint
   - Uses simple NLP (Counter, basic regex) — NO heavy models needed here
   - Detects Nigerian signals: pidgin words, local place/food mentions

3. task_a/review_generator.py
   - ReviewGenerator class with async generate() method
   - Constructs a detailed system prompt encoding the user's style fingerprint
   - Retrieves 3–5 example reviews from ChromaDB for few-shot context
   - Calls Claude claude-sonnet-4-20250514 to generate review text
   - System prompt must instruct Claude to:
     * Match the user's avg review length (±20%)
     * Match their formality score
     * Reflect their sentiment distribution
     * Use similar vocabulary richness
     * If nigerian_mode: incorporate Nigerian expressions naturally

4. task_a/rating_predictor.py
   - RatingPredictor class
   - predict(user_profile, item_details, review_text) → float
   - Strategy: prompt Claude with the generated review + user's rating history 
     to predict the rating, then clamp to [1.0, 5.0]
   - Also compute a rule-based fallback: user's avg_rating adjusted by 
     sentiment polarity of generated review

5. task_a/agent.py
   - UserModelingAgent orchestrating all steps above
   - async run(request: ReviewRequest) → ReviewResponse
   - Logs each step duration for debugging

6. task_a/evaluator.py
   - compute_rouge(generated, reference) → dict
   - compute_bertscore(generated, reference) → dict  
   - compute_rmse(predicted_ratings, actual_ratings) → float
   - run_batch_eval(test_samples) → EvalReport

<constraints>
- All LLM calls go through shared/llm_client.py (already scaffolded)
- Prompts must be stored as named constants at module top (not inline strings)
- Use async/await throughout
- Include docstrings on every class and public method
- The Nigerian adapter should be a toggle, not always-on
- Handle cases where review_history is empty (cold user)
</constraints>

<output_format>
Output each file completely with its path as a header comment. 
Include type hints everywhere. No truncation.
</output_format>