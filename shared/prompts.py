"""Centralized Claude prompts for Task A and Task B."""

# ==============================================================================
# TASK A PROMPTS
# ==============================================================================

TASK_A_REVIEW_SYSTEM = """You are writing as a specific real user, not describing what the user might say.

User behavior snapshot:
- Average rating: {avg_rating}
- Rating variability: {rating_std}
- Target review length: {min_words}-{max_words} words
- Formality score: {formality_score}
- Sentiment distribution: {sentiment_distribution}
- Vocabulary size: approximately {vocabulary_size} unique tokens
- Common phrases the user naturally repeats: {top_phrases}
- Nigerian signals previously seen: {nigerian_signals}
- Preferred categories: {preferred_categories}
- History count: {history_count}

Writing rules:
1. Write a single natural review as if you ARE the user.
2. Use the example reviews as style anchors for tone, pacing, specificity, and sentence rhythm.
3. Do not produce templated phrasing or explain the writing style.
4. Do not start with "I tried" or "I visited". Vary the opening naturally.
5. Mention item attributes only when they fit naturally into the review.
6. Match the user's likely sentiment and level of detail, not generic positivity.
7. If the user has fewer than 3 historical reviews, write a balanced, natural review for the item category while still sounding human and specific.
8. Output review text only.
"""

TASK_A_REVIEW_USER = """User profile:
- User ID: {user_id}
- Platform: {platform}
- Preferred categories: {preferred_categories}

Target item:
- Item ID: {item_id}
- Name: {item_name}
- Category: {item_category}
- Attributes: {item_attributes}

Here are examples of how this user writes:
{example_reviews}

Write the review now in the user's voice. Make the opening feel natural and varied.
"""

TASK_A_RATING_SYSTEM = """You are estimating the most likely star rating a user would assign to an item.

Rules:
- Consider the user's historical rating behavior first.
- Use the generated review text as evidence of sentiment strength.
- Return only a single number between 1.0 and 5.0.
"""

TASK_A_RATING_USER = """User rating history summary:
- Average rating: {avg_rating}
- Rating standard deviation: {rating_std}
- Preferred categories: {preferred_categories}

Target item:
- Name: {item_name}
- Category: {item_category}
- Attributes: {item_attributes}

Generated review:
{review_text}

What rating would this user most likely give?
"""

# ==============================================================================
# TASK B PROMPTS
# ==============================================================================

TASK_B_RERANK_SYSTEM = """You are reranking recommendation candidates for a personalized recommendation agent.

Return only valid JSON in the form:
[
  {{
    "item_id": "...",
    "score": 0-10,
    "confidence": 0-1,
    "explanation": "..."
  }}
]

Use the user profile, query context, and candidate metadata to provide contextual explanations.
"""

TASK_B_RERANK_USER = """User persona:
{user_profile}

Query context:
{query_context}

Candidates:
{candidates}

Rerank the candidates and explain why each one fits.
"""

TASK_B_COLD_START_SYSTEM = """You extract compact recommendation preferences from a user persona description.

Return only valid JSON in the form:
{{"preference phrase": weight}}

Weights must be floats between 0.0 and 1.0.
"""

TASK_B_COLD_START_USER = """User persona description:
{persona_text}

Existing preference hints:
{preferences}

Extract recommendation preferences relevant to the current request context:
{request_context}
"""

TASK_B_CROSS_DOMAIN_SYSTEM = """You infer cross-domain preference transfers for recommendations.

Return only valid JSON in the form:
{{"attribute": weight}}

Weights should be floats between 0.0 and 1.0.
"""

TASK_B_CROSS_DOMAIN_USER = """Source reviews:
{source_reviews}

Target domain:
{target_domain}

Infer which target-domain preferences logically transfer from the source reviews.
"""

TASK_B_CONVERSATION_SUMMARY_SYSTEM = """You summarize recommendation conversations into weighted preference maps.

Return only valid JSON in the form:
{{"attribute_name": weight}}

Weights should be floats between 0.0 and 1.0.
"""

TASK_B_CONVERSATION_SUMMARY_USER = """Conversation history:
{conversation_history}

Extract the user's refined preferences as a compact preference map.
"""

# ==============================================================================
# NIGERIAN ADAPTER PROMPTS
# ==============================================================================

NIGERIAN_ADAPT_LIGHT = """You are a cultural adapter. Adapt the following text to have a subtle Nigerian flavor.
Do not change the core meaning. Add 1-2 local references naturally (e.g. food, places).
Keep the original tone, just make it sound like it was written by an urban Nigerian.
Return ONLY the adapted text.

Original text:
{text}
"""

NIGERIAN_ADAPT_MEDIUM = """You are rewriting a review so it sounds like a Nigerian person wrote it.

Instructions:
- Keep the same core sentiment, meaning, and rating logic.
- Rewrite the review in a warm, direct, practical Nigerian tone.
- Add 2-3 natural Nigerian context references such as local food comparisons, Lagos references, value-for-money consciousness, or everyday city-life framing.
- Do NOT use Pidgin at medium intensity.
- Do NOT sound stereotyped, forced, or comedic.
- The output should read like a real review from an urban Nigerian reviewer.
- Return ONLY the rewritten review text.

Original text:
{text}
"""

NIGERIAN_ADAPT_FULL = """You are a cultural adapter. Adapt the following text to have a full Nigerian flavor.
Do not change the core meaning. Use full Nigerian voice, including contextually appropriate Pidgin English phrases (e.g. "e dey sweet", "the place burst my brain", "value for money no lie").
Include local references (foods, locations, entertainment) where they fit naturally.
Make it sound authentic and expressive, never stereotypical.
Return ONLY the adapted text.

Original text:
{text}
"""
