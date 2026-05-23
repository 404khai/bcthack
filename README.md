# BCT Hackathon LLM Agents

A submission for the DSN x BCT LLM Agent Hackathon featuring two containerized LLM-powered microservices for user modeling and recommendation.

## Quick Start (3 Commands)

```bash
# 1. Clone and setup
git clone https://github.com/404khai/bcthack
cd bcthack

# 2. Configure environment
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# 3. Start all services
docker-compose up --build
```

Services will be available at:
- **Task A (User Modeling)**: [http://localhost:8001/docs](http://localhost:8001/docs)
- **Task B (Recommendation)**: [http://localhost:8002/docs](http://localhost:8002/docs)
- **ChromaDB**: [http://localhost:8000](http://localhost:8000)

## Environment Setup

### Python Virtual Environment
```bash
# Create and activate virtual environment
python -m venv venv

# Windows (PowerShell)
venv\Scripts\Activate.ps1

# Windows (CMD)
venv\Scripts\activate.bat

# Mac/Linux
source venv/bin/activate

# Install all dependencies
pip install -r task_a/requirements.txt
pip install -r task_b/requirements.txt

# Install evaluation-only dependencies when needed
pip install -r eval/requirements.txt
```

### API Keys
Get your free Gemini API key at: https://aistudio.google.com/apikey
No billing required for the free tier (1,500 requests/day).
Add it to your .env file: `GEMINI_API_KEY=your_key_here`

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│              Shared Infrastructure               │
│  Vector Store (ChromaDB) + User Profile Store   │
│  Dataset Preprocessor (Yelp + Amazon + GoodR.)  │
└─────────────┬───────────────────────┬────────────┘
              │                       │
   ┌──────────▼──────────┐  ┌────────▼──────────────┐
   │   Task A Service    │  │   Task B Service       │
   │  /generate-review   │  │  /recommend            │
   │                     │  │  /recommend/chat       │
   │  UserPersonaBuilder │  │  ReasoningAgent        │
   │  StyleExtractor     │  │  ColdStartHandler      │
   │  ReviewGenerator    │  │  CrossDomainBridge     │
   │  RatingPredictor    │  │  ConversationManager   │
   └─────────────────────┘  └───────────────────────┘
              │                       │
   ┌──────────▼───────────────────────▼────────────┐
   │            FastAPI Gateway + Docker            │
   │          docker-compose (single stack)         │
   └────────────────────────────────────────────────┘
```

## Tech Stack

- **Framework**: FastAPI (async, OpenAPI docs, easy containerization)
- **LLM Backbone**: Google Gemini 2.5 Flash via `google-genai` Python SDK (free tier)
- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` (fast, free, local)
- **Vector Store**: ChromaDB (persistent, no external server, Docker-friendly)
- **Dataset Handling**: pandas + custom processors
- **Evaluation**: rouge-score, bert-score, scikit-learn (RMSE, NDCG, Hit Rate)
- **Containerization**: Docker + docker-compose

## Dataset Setup

### 1. Download Datasets

Place the following datasets in the `data/` directory:

1. **Yelp Open Dataset**: Download from [Yelp Dataset](https://www.yelp.com/dataset)
   - `yelp_academic_dataset_review.json`
   - `yelp_academic_dataset_user.json`
   - `yelp_academic_dataset_business.json`

2. **Amazon Reviews (McAuley)**: Download from [Amazon Reviews](https://cseweb.ucsd.edu/~jmcauley/datasets/amazon_v2/)
   - `Electronics.json (5 core)` (or subset)

3. **Goodreads (UCSD)**: Download from [Goodreads](https://cseweb.ucsd.edu/~jmcauley/datasets/goodreads.html)
   - `goodreads_reviews_spoiler_raw.json`
   - `goodreads_books.json`

### 2. Create Samples (Optional)

For development/testing, create sample files:

```bash
python -m data.create_samples
```

This creates 100-row sample files in `data/sample/test_fixtures/`.

### 3. Ingest Data into ChromaDB

Ensure your venv is activated before running any python commands

```bash
# Full ingestion (all datasets)
python -m data.ingest

# Partial ingestion
python -m data.ingest --skip-yelp  # Skip Yelp data
python -m data.ingest --skip-amazon  # Skip Amazon data
python -m data.ingest --skip-goodreads  # Skip Goodreads data

# Sample-only mode (first 100 users per dataset)
python -m data.ingest --sample-only
```

## API Documentation

### Task A: User Modeling Service

**Endpoint**: `POST http://localhost:8001/generate-review`

**Request**:
```json
{
  "user_id": "user_123",
  "platform": "yelp",
  "item_id": "business_456",
  "item_name": "Joe's Diner",
  "item_category": "Restaurants",
  "nigerian_intensity": "light"
}
```

**Response**:
```json
{
  "review_text": "The food was excellent and service was prompt...",
  "rating": 4.5,
  "confidence": 0.85,
  "style_notes": "Matches user's preference for detailed descriptions",
  "request_id": "req_789"
}
```

**cURL Example**:
```bash
curl -X POST "http://localhost:8001/generate-review" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "platform": "yelp",
    "item_id": "test_business",
    "item_name": "Test Restaurant",
    "item_category": "Restaurants",
    "nigerian_intensity": "light"
  }'
```

### Task B: Recommendation Service

**Endpoint**: `POST http://localhost:8002/recommend`

**Request**:
```json
{
  "user_id": "user_123",
  "platform": "yelp",
  "category": "restaurants",
  "top_k": 10,
  "nigerian_mode": false,
  "session_id": "session_456"
}
```

**Response**:
```json
{
  "recommendations": [
    {
      "item_id": "business_789",
      "item_name": "Lagos Kitchen",
      "category": "Nigerian Restaurant",
      "score": 0.92,
      "explanation": "Based on your love for spicy food and previous reviews of African cuisine..."
    }
  ],
  "thinking": "User has reviewed 15 restaurants with average rating 4.2...",
  "session_id": "session_456",
  "request_id": "req_101112"
}
```

**cURL Example**:
```bash
curl -X POST "http://localhost:8002/recommend" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "platform": "yelp",
    "category": "restaurants",
    "top_k": 5,
    "nigerian_mode": true,
    "session_id": "test_session"
  }'
```

## Evaluation

### Task A Evaluation

```bash
# Install eval extras first
pip install -r eval/requirements.txt

# Run Task A evaluation
python -m eval.run_task_a_eval

# Output includes:
# - ROUGE-1 and ROUGE-L scores (text similarity)
# - BERTScore-F1 (semantic similarity)
# - RMSE and MAE (rating accuracy)
# - Results saved to eval_results_task_a.json and eval_results_task_a.csv
```

### Task B Evaluation

```bash
# Install eval extras first
pip install -r eval/requirements.txt

# Run Task B evaluation
python -m eval.run_task_b_eval

# Output includes:
# - NDCG@10 (ranking quality)
# - Hit Rate@10 (coverage of held-out items)
# - Cold-start performance metrics
# - Results saved to eval_results_task_b.json and eval_results_task_b.csv
```

## Design Decisions

### 1. Why ChromaDB?
- **Persistent storage**: Data survives container restarts
- **Local operation**: No external dependencies for hackathon environment
- **Metadata filtering**: Essential for user-specific and category-specific queries
- **Docker-friendly**: Official container image available

### 2. Why Reasoning-First Agent Loop?
- **Transparency**: Judges can see the "thinking" field in responses
- **Better retrieval**: Formulated queries based on understanding, not just keywords
- **Cold-start handling**: Explicit reasoning about user preferences before retrieval
- **Cross-domain inference**: Structured preference mapping between domains

### 3. Why Nigerian Contextualization Layer?
- **Bonus marks**: Explicitly mentioned in hackathon brief
- **Cultural relevance**: Adapts recommendations to Nigerian context
- **Toggleable**: Can be disabled for evaluation, enabled for demos
- **Three intensity levels**: Light (references), Medium (tone), Full (Pidgin phrases)

### 4. Why Multi-Stage Docker Builds?
- **Smaller images**: Runtime images exclude build dependencies
- **Security**: Non-root users in runtime stage
- **Reproducibility**: Consistent builds across environments
- **Health checks**: Automatic monitoring of service health
- **Faster rebuilds**: pip cache and CPU-only torch avoid repeated heavyweight ML downloads

## Known Limitations

1. **Session State**: Task B conversation state is in-memory only (not persisted to database)
2. **Scalability**: Designed for hackathon-scale evaluation, not production loads
3. **Dataset Size**: Uses sampled datasets (100-1000 users per platform)
4. **Cold-Start**: Limited demographic signals for true cold-start users
5. **Cross-Domain**: Inference based on semantic similarity, not explicit user feedback

## Future Work

1. **Redis Integration**: Persistent session storage for Task B conversations
2. **Fine-Tuned Embeddings**: Domain-specific embedding models for better retrieval
3. **A/B Testing Framework**: Compare different recommendation strategies
4. **Production Monitoring**: Metrics collection and alerting
5. **User Feedback Loop**: Incorporate explicit feedback into preference models

## Project Structure

```
bcthack/
├── docker-compose.yml          # Full stack orchestration
├── .env.example               # Environment template
├── Makefile                   # Development commands
├── shared/                    # Common infrastructure
│   ├── embeddings.py          # Sentence-transformers wrapper
│   ├── vector_store.py        # ChromaDB client
│   ├── llm_client.py          # Anthropic SDK with retries
│   ├── user_profile.py        # UserProfile dataclass
│   ├── nigerian_adapter.py    # Cultural contextualization
│   └── prompts.py            # Centralized Claude prompts
├── task_a/                    # User Modeling Service
│   ├── main.py               # FastAPI app
│   ├── agent.py              # UserModelingAgent
│   ├── persona_builder.py    # Style fingerprint extraction
│   ├── review_generator.py   # LLM-based review generation
│   ├── rating_predictor.py   # Rating prediction
│   ├── evaluator.py          # ROUGE, BERTScore, RMSE
│   ├── schemas.py            # Pydantic models
│   ├── Dockerfile            # Multi-stage build
│   └── requirements.txt       # Python dependencies
├── task_b/                    # Recommendation Service
│   ├── main.py               # FastAPI app
│   ├── agent.py              # RecommendationAgent
│   ├── retriever.py          # MultiSourceRetriever
│   ├── cold_start.py         # Cold-start handling
│   ├── cross_domain.py       # Cross-domain preference bridge
│   ├── conversation.py        # Conversation state manager
│   ├── ranker.py             # LLM-based reranking
│   ├── schemas.py            # Pydantic models
│   ├── Dockerfile            # Multi-stage build
│   └── requirements.txt      # Python dependencies
├── data/                      # Dataset processing
│   ├── ingest.py             # Master ingestion script
│   ├── yelp_processor.py     # Yelp data processor
│   ├── amazon_processor.py   # Amazon data processor
│   ├── goodreads_processor.py # Goodreads data processor
│   ├── create_samples.py     # Test fixture generation
│   └── sample/               # Sample data files
└── eval/                      # Evaluation harness
    ├── run_task_a_eval.py    # Task A evaluation
    └── run_task_b_eval.py    # Task B evaluation
```

## Development Commands

```bash
# Build all services
make build

# Start all services
make up

# Stop all services
make down

# Run Task A evaluation
make eval-a

# Run Task B evaluation
make eval-b

# Ingest data into ChromaDB
make ingest

# View logs
make logs

# Run tests (if available)
make test
```

## License

This project is developed for the DSN x BCT LLM Agent Hackathon. All rights reserved.
