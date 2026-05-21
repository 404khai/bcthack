# Task A Solution Paper Brief

SECTION 1: Problem Framing
Target length: 0.5 pages
Core argument: Task A is an exercise in behavioral simulation, because the system must reconstruct how a user judges and writes, not just what categories they like.

PROSE:
Task A asks a narrower and harder question than standard recommendation. The input is a user's review history. The output is not a ranked list, but a simulated future action: what rating this user would likely assign to an unseen item, and what review text they would write in their own voice. In engineering terms, this means the system has to recover both preference and expression. A model that only learns that a user likes restaurants or electronics is incomplete. It also has to learn whether that user writes tersely or at length, whether they are generous or volatile in scoring, whether they sound formal or casual, and whether they use recurring phrases that make the writing recognizable as theirs.

That distinction is why we framed Task A as user modeling rather than preference aggregation. In `shared/user_profile.py`, the center of gravity is the `StyleFingerprint` dataclass, not a sparse preference vector. We model `avg_rating` and `rating_std` separately because they capture different behavior. A user with `avg_rating=4.2` and `rating_std=0.3` behaves like a reliable enthusiast. A user with `avg_rating=3.5` and `rating_std=1.2` has a wider swing between good and bad experiences. Those two users should not produce the same review structure even if they review items from the same category.

The practical differentiator from a baseline system is few-shot grounding with the user's own historical reviews. In `task_a/review_generator.py`, the generator builds a prompt from the fingerprint and then injects up to three formatted example reviews, retrieved from the user's history and capped from a pool of up to five examples. This matters because style is easier to imitate from concrete text than from summary statistics alone. The review examples carry pacing, sentence rhythm, typical openings, and how much concrete detail the user tends to include.

This framing also explains why the early broken versions failed so visibly. When the LLM path silently collapsed to fallback templates, the system still produced text, but it was not user modeling. It was string assembly. The fixes that mattered were the ones that restored behavioral evidence: the real fingerprint, the real review examples, and the actual LLM path.

KEY INSIGHT LINE:
Task A works only when the system treats rating behavior and writing style as first-class signals, not as side effects of category preference.

SECTION 2: System Architecture
Target length: 0.75 pages
Core argument: The architecture separates user modeling from recommendation so each service can evolve independently while sharing one vector memory layer.

PROSE:
The deployed system uses two FastAPI microservices: Task A on port `8001` and Task B on port `8002`. Both services read from the same ChromaDB instance, which stores three collections: `users` with 394 documents, `items` with 499 documents, and `reviews` with 5212 documents in sample mode. We kept the services separate because the workloads are different. Task A is generation-heavy and centered on persona reconstruction, while Task B is retrieval-heavy and centered on recommendation planning. Keeping them isolated simplified debugging, allowed different request paths and logs per task, and avoided coupling user-modeling latency to recommendation traffic.

The architecture is simple enough to reason about:

```text
Raw Yelp / Amazon / Goodreads data
        |
        v
Dataset processors + deterministic 80/20 user split
        |
        v
UserProfileBuilder + ChromaDB ingestion
        |
        +--------------------------+
        |                          |
        v                          v
  ChromaDB users/items/reviews   Task A service (:8001)
        |                          |
        |                          +--> fetch user document
        |                          +--> rebuild StyleFingerprint
        |                          +--> retrieve few-shot reviews
        |                          +--> Gemini generate review
        |                          +--> predict rating
        |                          +--> optional Nigerian adaptation
        |
        +-----------------------> Task B service (:8002)
```

We chose ChromaDB because the project needed one persistence layer that could hold user summaries, item summaries, and free-form reviews while also supporting semantic lookup. That was especially useful for Task A because the system stores a searchable user document via `UserProfile.to_document()` in `shared/user_profile.py`, then reconstructs missing fields later from that text. A stricter relational schema would have been cleaner for exact retrieval, but ChromaDB let us keep text and metadata together and reuse the same store across both tasks.

The embedding model is `sentence-transformers/all-MiniLM-L6-v2`. It is not the most expressive encoder available, but it is fast, cheap, and sufficient for a hackathon setting where retrieval quality needs to be good enough without making ingestion slow. The LLM layer uses Gemini 2.5 Flash through the `google-genai` SDK in `shared/llm_client.py`. The reasons were practical: a long context window, acceptable generation quality for review text, and a free tier that made the first working version feasible. That same free tier later became a reliability constraint because multiple LLM calls per request compound quickly.

The ingestion path combines three dataset-specific processors for Yelp, Amazon, and Goodreads. In sample mode, the system ingests 100 users per source: Yelp contributes 327 items, 372 training reviews, and 125 held-out test reviews; Amazon contributes 144 items and 1677 reviews; Goodreads contributes 28 items, 2702 training reviews, and 581 held-out test reviews. The train/test split is deterministic at the user level: the last 20 percent of each user's chronologically sorted reviews are held out for evaluation.

KEY INSIGHT LINE:
The cleanest architectural decision was not the model choice, but isolating Task A and Task B behind one shared ChromaDB memory layer.

SECTION 3: StyleFingerprint: Behavioral DNA
Target length: 1 page
Core argument: The most important contribution in Task A is the `StyleFingerprint`, because it turns raw review history into a compact behavioral representation the generator can actually condition on.

PROSE:
The core modeling object is `StyleFingerprint` in `shared/user_profile.py`. It has eight fields, and each field exists because it controls a different failure mode in generated reviews.

`avg_rating` is the user's central tendency, computed as the mean of historical star ratings in `build_style_fingerprint()`. `rating_std` is the square root of the population variance over those ratings via `_std_dev()`. `avg_review_length` is the mean token count per review, where tokenization uses `TOKEN_PATTERN = re.compile(r"[A-Za-z']+")`. `vocabulary_size` counts unique lowercase tokens across the corpus. `top_phrases` comes from `_extract_top_phrases()`, which counts bi-grams and tri-grams while filtering phrase edges through `PHRASE_STOPWORDS`. `sentiment_profile` is a normalized three-way distribution built from `_classify_sentiment()`, which compares hits from `POSITIVE_WORDS` and `NEGATIVE_WORDS`. `formality_score` comes from `_estimate_formality()`, which starts from `0.5` and adjusts by formal-word hits, informal-word hits, and contraction count. `nigerian_signals` comes from `_detect_nigerian_signals()`, which intersects tokenized text with `NIGERIAN_TERMS`, including words such as `abeg`, `buka`, `jollof`, `lagos`, `naija`, `shoprite`, `suya`, and `wahala`.

The storage problem was less elegant. ChromaDB metadata is flat key-value storage. `StyleFingerprint` is not flat. It includes a nested dictionary for sentiment and lists for phrases and Nigerian signals. The compromise appears in `UserProfile.to_metadata()` and `UserProfile.to_document()` in `shared/user_profile.py`. Some fields such as `avg_rating`, `rating_std`, `avg_review_length`, `vocabulary_size`, and `formality_score` are stored directly in metadata. Lists such as `preferred_categories` and `nigerian_signals` are flattened into comma-separated strings. The richer representation is pushed into the user document string:

```text
Average rating {avg_rating:.2f} with rating deviation {rating_std:.2f}.
Average review length {avg_review_length:.1f} words, vocabulary size {vocabulary_size},
formality {formality_score:.2f}. Top phrases: {phrases}. Sentiment profile: {sentiment}.
```

That design made retrieval possible, but reconstruction messy. In `task_a/agent.py`, `_rebuild_fingerprint_from_chroma()` has to parse part of the fingerprint back out of document text with regex because not every field is guaranteed to exist as clean metadata. The exact patterns are:

```python
r"rating deviation ([\\d.]+)"
r"formality ([\\d.]+)"
r"Top phrases: ([^.]+)\\."
rf"{key}=([\\d.]+)"
```

This reconstruction logic was not incidental. It became necessary after we discovered that several fields the generator depended on were stored only inside the Chroma document, not in metadata. Without that parse step, users collapsed toward default values like `rating_std=0.0`, a sentiment prior of `0.34/0.33/0.33`, and empty `top_phrases`.

The best engineering case study in this section is the Yelp ID bug. Some Yelp user IDs already begin with `_`. During ingestion, those IDs were prefixed with the platform, producing values like `yelp__BcWyKQL16ndpBdggh2kNA` in the `users` collection. But some reviews kept the raw `_BcWyKQL16ndpBdggh2kNA` form in their metadata. That meant a direct lookup by one canonical user ID could find the user summary but fail to find the user's review examples. The fix was not a cosmetic rename. It required candidate-based lookup that tries multiple user ID formats before concluding that history is missing. This is the kind of bug that only shows up when storage conventions drift across collections.

KEY INSIGHT LINE:
`StyleFingerprint` worked as behavioral DNA only after we treated storage format as part of the modeling problem, not just a persistence detail.

SECTION 4: Review Generation Pipeline
Target length: 1 page
Core argument: The review generator succeeds because it combines reconstructed behavioral features with the user's own review text, then uses a deterministic fallback only as a last resort.

PROSE:
The Task A orchestration path lives in `task_a/agent.py` under `UserModelingAgent.run()`. The pipeline is explicit and easy to trace in logs. Step 1 fetches the user document from ChromaDB with `self.vector_store.get_by_id("users", request.user_persona.user_id)`. Step 2 rebuilds the `StyleFingerprint` either from Chroma metadata plus document text or, if the user is absent from Chroma, from the request payload through `PersonaBuilder.build()`. Step 3 converts the incoming history into `ReviewRecord` objects and assembles a `UserProfile`. Step 4 calls `ReviewGenerator.generate()` to prepare a system prompt, pull few-shot examples, and ask Gemini for review text. Step 5 sends the generated review through `RatingPredictor.predict()`. Step 6 optionally applies `NigerianContextAdapter.adapt_review()` if `nigerian_mode=True`. The agent records timings for `persona_builder`, `review_generator`, and `rating_predictor`, which made it easier to isolate slow or broken stages.

Few-shot retrieval is the most effective design choice in the generator. In `task_a/review_generator.py`, `retrieve_example_reviews()` first prefers local `user_profile.review_history` and returns the first available non-empty examples, capped at five. If local history is missing, it falls back to `vector_store.query_reviews_for_user()`. Earlier debugging showed why this matters: when example retrieval failed because of the user ID mismatch, the generated reviews lost the user's pacing and became generic. Once the generator had access to real examples again, the outputs started reflecting actual user habits, not just the summary statistics in the fingerprint.

The system prompt in `shared/prompts.py` encodes the user's behavioral signature directly. It passes `avg_rating`, `rating_std`, `formality_score`, `sentiment_distribution`, `vocabulary_size`, `top_phrases`, `nigerian_signals`, `preferred_categories`, and `history_count`. It also communicates an explicit review-length band via `Target review length: {min_words}-{max_words} words`, where `min_words` is `max(20, int(avg_review_length * 0.8))` and `max_words` is `max(30, int(avg_review_length * 1.2))` in `task_a/review_generator.py`. Formality is not hand-waved. It is surfaced as `Formality score: {formality_score}` so the model can infer whether to write in a measured or casual register. The prompt also bans templated openings by stating: `Do not start with "I tried" or "I visited". Vary the opening naturally.`

Rating prediction is more conservative than review generation. In `task_a/rating_predictor.py`, `RatingPredictor.predict()` computes a `fallback_rating` first via `_rule_based_fallback()`. That function starts from the mean historical rating and then shifts the score based on sentiment polarity in the generated review, with positive polarity adding up to `0.8` at `0.35` per unit and negative polarity subtracting up to `0.8` at `0.45` per unit before clamping to `[1.0, 5.0]`. If an LLM client is available, the predictor asks for a single number using `TASK_A_RATING_SYSTEM` and parses the result with `RATING_PATTERN = re.compile(r"([1-5](?:\\.\\d+)?)")`. In the current code, this path still goes through the legacy `AnthropicLLMClient` name, which is now a compatibility alias to `GeminiLLMClient` in `shared/llm_client.py`.

The fallback review path deserves to be documented honestly because it was not just a safety net. For a while it was effectively the whole product. `FALLBACK_REVIEW_TEMPLATE` in `task_a/review_generator.py` is:

```text
I tried {item_name} in the {item_category} category and found it {tone}.
{attribute_sentence} {phrase_sentence}{sentiment_sentence}
```

Before the LLM client mismatch, dotenv ordering bug, and Chroma path bug were fixed, this template fired for every request. After the fixes, it remains only as the final fallback when the LLM path is unavailable or fails.

KEY INSIGHT LINE:
The generator stopped sounding generic only after it had both kinds of evidence at once: abstract style statistics and concrete user-authored review examples.

SECTION 5: Nigerian Contextualization
Target length: 0.5 pages
Core argument: Nigerian mode is implemented as a second-stage cultural rewrite, which improves local relevance but introduces an extra failure surface.

PROSE:
Nigerian contextualization is handled after review generation in `shared/nigerian_adapter.py`. This is not a prompt flag inside the first generation pass. It is a second LLM call implemented by `NigerianContextAdapter.adapt_review()`. The adapter is enabled either explicitly in code or by `NIGERIAN_MODE` from the environment through `from_env()`. That separation made the feature modular, but it also meant Nigerian mode doubled the dependence on LLM availability and quotas.

Detection starts with lexicons. In `shared/user_profile.py`, `NIGERIAN_TERMS` includes markers such as `abeg`, `buka`, `chop`, `danfo`, `jollof`, `lagos`, `naija`, `shoprite`, `suya`, and `wahala`. `task_a/persona_builder.py` extends this idea with `PIDGIN_TERMS` and `LOCAL_REFERENCES`, including `ikeja`, `yaba`, `jumia`, and `abuja`. Those signals are used to populate `nigerian_signals` in the fingerprint so the main review prompt can see whether the user already writes with local references.

There are three adaptation intensities in `shared/prompts.py`. `NIGERIAN_ADAPT_LIGHT` adds one or two subtle local references while preserving tone. `NIGERIAN_ADAPT_MEDIUM` asks for a warm, practical Nigerian tone with two to three local references but explicitly bans Pidgin. `NIGERIAN_ADAPT_FULL` allows stronger Nigerian voice, including contextually appropriate Pidgin phrases such as `e dey sweet` or `value for money no lie`. The adapter selects among these prompts and asks Gemini to rewrite the full review while preserving sentiment and meaning.

This feature solved an explicit hackathon bonus criterion and produced visibly better localized outputs. The confirmed working tests showed the model naturally introducing Lagos and Lekki references for Nigerian mode. But it also surfaced a known limitation: at `medium` and `full` intensity, the second LLM call can truncate mid-sentence. The current code mitigates this by logging input and output lengths, checking `last_finish_reason`, and discarding the adapted text if it is less than 60 characters or shorter than 60 percent of the original length. That is a guardrail, not a real fix.

KEY INSIGHT LINE:
Nigerian mode improved cultural relevance because it was treated as a rewrite problem, but that same decision added a second LLM failure point to every adapted request.

SECTION 6: Experiments & Evaluation
Target length: 0.75 pages
Core argument: Even before running the full metric suite, the debugging journey already produced three meaningful ablations that explain where the quality gains came from.

PROSE:
The evaluation plan is implemented in `task_a/evaluator.py`. It computes ROUGE-L with stemming through `rouge_score`, BERTScore precision, recall, and F1 through `bert_score`, and RMSE through `sklearn.metrics.mean_squared_error`. The data protocol is deterministic: for each user, the last 20 percent of chronologically sorted reviews are held out as test data. Across the sample datasets, that yields 706 total held-out reviews. The evaluation question is straightforward: given training history only, how close is the generated review to the held-out reference review, and how close is the predicted star rating to the held-out rating.

The first natural ablation is template versus LLM. Before the LLM path was fixed, every output fell through to the deterministic fallback template in `task_a/review_generator.py`. The structure was constant and easy to spot. After the Gemini path was restored, outputs became more varied and domain-appropriate. The Yelp user `yelp__BcWyKQL16ndpBdggh2kNA`, who has 65 reviews with `avg_rating=3.615`, `avg_review_length=78.09`, and `vocabulary_size=1632`, produced the review opening: `Stopped by Zesty Tsunami in Las Vegas for a quick lunch. The Hawaiian Fusion idea sounded promising...` That is qualitatively different from the fallback sentence frame.

The second ablation is empty fingerprint versus real fingerprint. Before the Chroma path mismatch was fixed, the system behaved as if the user store were empty. That pushed many requests toward default values like `avg_rating=3.5` and `rating_std=0.0`. After the fix, real user values flowed back into the prompt. For the Amazon user `amazon_A1K4G5YJDJQI6Q`, the system recovered `avg_rating=2.8`, `avg_review_length=285.8`, and `vocabulary_size=1788`, then generated: `Having a portable charger is pretty much essential these days, so I picked up the Anker 20000mAh power bank...` The improvement is not cosmetic. The prompt is conditioning on real behavioral variance rather than a default persona.

The third ablation is no few-shot grounding versus five grounded examples. Before the user ID lookup fix, example retrieval often returned nothing because user identifiers did not line up across collections. After candidate-based matching restored access to the user's review history, the generator could anchor tone and detail in real text. This was the change that made outputs feel attributable to a user instead of attributable to a category template.

Rate limiting became part of the evaluation story because the free-tier Gemini quota is a real system constraint, not an abstract concern. `shared/llm_client.py` now enforces `FREE_TIER_MODE` throttling by spacing calls three seconds apart across client instances and parses retry delays from 429 quota errors with `re.search(r"retry in ([\\d.]+)s", ...)`. This matters because one Task A request can involve review generation, optional Nigerian adaptation, and rating prediction. Even a well-designed pipeline can exhaust a small daily budget if each stage makes its own call.

KEY INSIGHT LINE:
The biggest quality jumps came from restoring missing evidence, not from clever prompting: real fingerprints, real few-shot examples, and a live LLM path.

SECTION 7: Known Limitations & Future Work
Target length: 0.5 pages
Core argument: The current Task A system is usable and instructive, but several design shortcuts remain visible and should be addressed before claiming production readiness.

PROSE:
The first known limitation is Nigerian adapter truncation at `medium` and `full` intensity. The current safeguard only rejects outputs that are obviously too short; it does not guarantee that a long but partially degraded rewrite is actually good. The second limitation is representational: important fingerprint fields are still split between metadata and document text, which forces regex reconstruction in `task_a/agent.py`. This works, but it is brittle and expensive compared with storing a canonical structured representation. The third limitation is evaluation scale. The current held-out set has 706 reviews across three sample datasets. That is enough to compare versions, but too small to claim stable cross-domain generalization.

There are also a few implementation scars worth documenting. Some legacy naming remains in the codebase: `shared/prompts.py` still opens with `Centralized Claude prompts`, and `task_a/rating_predictor.py` still imports `AnthropicLLMClient`, which is now just an alias to Gemini. More importantly, `_get_llm_client()` in `rating_predictor.py` still checks `ANTHROPIC_API_KEY`, so the practical rating path can fall back to rules unless that legacy variable is present. This does not invalidate the system, but it is the kind of migration debt that should be closed explicitly rather than ignored.

Future work is clear. First, run full ingestion instead of the 100-user sample subsets, because user modeling quality depends on varied histories. Second, store all `StyleFingerprint` fields explicitly in Chroma metadata or a companion structured store so retrieval does not depend on parsing prose. Third, fine-tune or replace the embedding model with one trained on review text to improve cross-platform semantic retrieval. Fourth, stream review output to reduce the perceived latency introduced by LLM calls and free-tier throttling. Fifth, close the loop by feeding subsequent user feedback back into the stored profile so the persona evolves after deployment.

KEY INSIGHT LINE:
The main limitation is not that the system fails outright, but that several successful behaviors still depend on recovery logic that should eventually become first-class design.
