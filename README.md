# BCT Hackathon LLM Agents

This repository contains the Phase 1 scaffold for a DSN x BCT hackathon submission. It is organized as two FastAPI microservices backed by shared LLM, embedding, and retrieval utilities.

## Services

- `task_a`: user modeling service that generates simulated reviews and star ratings.
- `task_b`: recommendation service that returns ranked recommendations with reasoning and explanations.
- `shared`: common infrastructure for Anthropic access, ChromaDB, embeddings, user profile modeling, and Nigerian contextualization.
- `data`: dataset processors and ingestion utilities for Yelp, Amazon Reviews, and Goodreads subsets.
- `eval`: lightweight evaluation entrypoints for both tasks.

## Local development

1. Copy `.env.example` to `.env` and fill in `ANTHROPIC_API_KEY`.
2. Install Docker Desktop or create a Python 3.11 virtual environment.
3. Start the services:

```bash
docker compose up --build
```

4. Open the generated docs:

- Task A: [http://localhost:8001/docs](http://localhost:8001/docs)
- Task B: [http://localhost:8002/docs](http://localhost:8002/docs)

## Data pipeline

The ingestion pipeline reads newline-delimited JSON examples from `data/sample/`, normalizes them into `UserProfile` objects, and writes users, items, and reviews into ChromaDB collections.

```bash
python -m data.ingest --use-sample-data
```

## Phase 1 scope

Phase 1 delivers:

- the project scaffold and package boundaries,
- Docker and compose orchestration,
- shared embedding, LLM, and vector store abstractions,
- dataset processors and a master ingestion command,
- Task A and Task B FastAPI service stubs with `/health` endpoints.

Subsequent phases will fill in richer review generation, retrieval reasoning, multi-turn conversation, and evaluation detail.
