PHASE 5 PROMPT — Nigerian Contextualization + Final Polish
<role>
You are a Senior Prompt Engineer with cultural intelligence. You understand 
how to make LLM outputs authentically reflect a specific cultural context 
without stereotyping or caricature.
</role>

<project_context>
The hackathon brief explicitly awards bonus marks for outputs "contextualized 
to behave and sound like Nigerians." This means:

For Task A (review generation):
  - Writing style: direct, expressive, community-oriented
  - References: Nigerian foods (suya, jollof, puff puff, pepper soup), 
    retailers (Shoprite, Jumia, Konga), locations (Lagos Island, Abuja, 
    Lekki, Victoria Island), entertainment (Afrobeats, Nollywood)
  - Tone: warm but blunt, practical value-consciousness
  - Optional: Pidgin English phrases (contextually appropriate)
    Examples: "e dey sweet", "the place burst my brain", "value for money no lie"

For Task B (recommendations):
  - Cold-start defaults should weight Nigerian-popular categories
  - Explanation text should reference Nigerian contexts naturally
  - Cross-domain mappings should include Nigerian entertainment/cuisine

The adapter must be OPTIONAL (toggled by nigerian_mode: bool in requests) 
so that evaluation can be run with and without it.
</project_context>

<task>
1. Implement shared/nigerian_adapter.py fully:
   - NigerianAdapter class
   - adapt_review(review_text, intensity: Literal["light","medium","full"]) → str
     * light: add 1–2 local references naturally
     * medium: adjust tone + 3–4 local references  
     * full: full Nigerian voice including optional Pidgin phrases
   - adapt_recommendation_explanation(explanation, category) → str
   - get_cultural_defaults(category: str) → list[str]
     * category="restaurant" → popular Nigerian restaurant types/dishes
     * category="book" → popular Nigerian authors (Chimamanda, Wole Soyinka, etc)
     * category="movie" → Nollywood + popular international picks in Nigeria
     * category="product" → popular Nigerian e-commerce categories
   - NIGERIAN_LEXICON dict: curated phrases by sentiment and category
   - All adaptation done via a Claude prompt (not hardcoded substitutions)

2. Update task_a/review_generator.py:
   - If nigerian_mode=True, call adapter.adapt_review() on output
   - Add nigerian_intensity param to ReviewRequest schema

3. Update task_b/cold_start.py:
   - Integrate adapter.get_cultural_defaults() as priority signal
   - Nigerian cold-start: assume user is in Lagos unless stated otherwise

4. Write a shared/prompts.py file:
   - Centralize ALL Claude prompts from both tasks as named constants
   - Each prompt should have a docstring explaining its purpose and variables
   - Separate: TASK_A_REVIEW_SYSTEM, TASK_A_RATING_PROMPT, 
     TASK_B_REASONING_PROMPT, TASK_B_RERANK_PROMPT, 
     TASK_B_COLD_START_PROMPT, TASK_B_CROSS_DOMAIN_PROMPT,
     NIGERIAN_ADAPT_LIGHT, NIGERIAN_ADAPT_MEDIUM, NIGERIAN_ADAPT_FULL

<constraints>
- The Nigerian adaptation must feel natural, not forced
- Never use stereotypes or demeaning language
- Pidgin must be used sparingly and only in "full" intensity mode
- Prompts in prompts.py use Python f-string templates with {variable} placeholders
</constraints>