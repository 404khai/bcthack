PHASE 1 PROMPT — Project Scaffold & Data Pipeline
<role>
You are a Senior Python Backend Engineer specializing in LLM systems, 
RAG pipelines, and containerized microservices. You write production-grade, 
modular, well-documented code.
</role>

<project_context>
We are building a submission for the DSN x BCT LLM Agent Hackathon. The system 
consists of TWO FastAPI microservices orchestrated via docker-compose:

1. Task A — User Modeling Service: takes a user persona + item details, 
   generates a simulated review (text + star rating) mimicking that user's style.

2. Task B — Recommendation Service: takes a user persona, reasons about their 
   preferences, and returns ranked personalized recommendations with explanations.

Datasets: Yelp Open Dataset, Amazon Reviews (McAuley/UCSD), Goodreads (UCSD).
LLM: Anthropic Claude via the `anthropic` Python SDK (API key via env var).
Embeddings: sentence-transformers (all-MiniLM-L6-v2, local).
Vector store: ChromaDB (persistent, local volume).
Evaluation: rouge-score, bert-score, scikit-learn.
</project_context>

<task>
Scaffold the entire project. Create the following structure:

bcthack/
├── docker-compose.yml
├── .env.example
├── README.md
├── shared/
│   ├── __init__.py
│   ├── embeddings.py          # sentence-transformers wrapper
│   ├── vector_store.py        # ChromaDB client (collections: users, items, reviews)
│   ├── llm_client.py          # Anthropic SDK wrapper with retry logic
│   ├── user_profile.py        # UserProfile dataclass + builder
│   └── nigerian_adapter.py    # Nigerian contextualization toggle
├── data/
│   ├── __init__.py
│   ├── yelp_processor.py      # Yelp JSON → UserProfile list
│   ├── amazon_processor.py    # Amazon JSON → UserProfile list
│   ├── goodreads_processor.py # Goodreads JSON → UserProfile list
│   ├── ingest.py              # Master ingestion script (runs all three)
│   └── sample/                # 100-row sample JSONs for dev/testing
├── task_a/
│   ├── __init__.py
│   ├── main.py                # FastAPI app
│   ├── agent.py               # UserModelingAgent
│   ├── persona_builder.py     # Extracts style fingerprint from history
│   ├── review_generator.py    # LLM-based review + rating generation
│   ├── rating_predictor.py    # Rating accuracy logic
│   ├── evaluator.py           # ROUGE, BERTScore, RMSE computation
│   ├── schemas.py             # Pydantic request/response models
│   ├── Dockerfile
│   └── requirements.txt
├── task_b/
│   ├── __init__.py
│   ├── main.py                # FastAPI app
│   ├── agent.py               # RecommendationAgent (reasoning loop)
│   ├── retriever.py           # ChromaDB RAG retrieval
│   ├── cold_start.py          # Cold-start handler (content-based fallback)
│   ├── cross_domain.py        # Cross-domain preference bridge
│   ├── conversation.py        # Multi-turn conversation state manager
│   ├── ranker.py              # LLM-based re-ranking with explanations
│   ├── schemas.py             # Pydantic request/response models
│   ├── Dockerfile
│   └── requirements.txt
└── eval/
    ├── run_task_a_eval.py
    └── run_task_b_eval.py

<constraints>
- Python 3.11
- FastAPI with async endpoints
- Pydantic v2 for all schemas
- All secrets via environment variables (never hardcoded)
- Each service runs independently on its own port (Task A: 8001, Task B: 8002)
- docker-compose mounts a shared ./data volume and ./chroma_db volume
- Include health check endpoints: GET /health on both services
- Add OpenAPI descriptions to every endpoint
- shared/ is a local package imported by both services (use PYTHONPATH in Docker)
</constraints>

<output_format>
Output every file in full. For each file, show the path as a comment header, 
then the complete file contents. Do not truncate. Do not use placeholders.
Start with docker-compose.yml, then .env.example, then shared/, then data/, 
then task_a/ and task_b/ scaffolds (main.py + schemas.py only for now), 
then eval/.
</output_format>