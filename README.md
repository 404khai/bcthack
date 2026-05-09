
# BCT Hackathon LLM Agents

This repository contains the evolving hackathon implementation for a DSN x BCT submission. It is organized as two FastAPI microservices backed by shared LLM, embedding, retrieval, and vector-store utilities.

## Services

- `task_a`: user modeling service that generates simulated reviews and star ratings.
- `task_b`: recommendation service that reasons before retrieval and returns ranked recommendations with explanations.
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

## Current scope

The repository now includes:

- Phase 1 scaffold, Docker orchestration, and shared infrastructure.
- Phase 2 Task A persona analysis, review generation, rating prediction, and evaluation utilities.
- Phase 3 Task B reasoning-first recommendation flow, multi-source retrieval, cold-start handling, cross-domain inference, reranking, and chat endpoints.

## Task B session note

Task B conversation state is stored in memory for hackathon speed and simplicity. Session history is keyed by `session_id`, survives only for the lifetime of the running process, and is not yet backed by Redis or a database.
