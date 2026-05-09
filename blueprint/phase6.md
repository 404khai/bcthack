PHASE 6 PROMPT — Evaluation Harness & Docker Finalization
<role>
You are a DevOps/MLOps engineer finalizing a hackathon submission. 
You care about reproducibility, clean READMEs, and making judges' 
lives easy.
</role>

<task>
1. Complete eval/run_task_a_eval.py:
   - Loads test split from data/splits.json
   - For each test review, calls Task A service via HTTP
   - Computes ROUGE-1, ROUGE-L, BERTScore-F1, RMSE
   - Outputs a formatted table + saves eval_results_task_a.json

2. Complete eval/run_task_b_eval.py:
   - Loads test users from splits.json
   - For each user, calls Task B service, gets top-10 recommendations
   - Computes NDCG@10 and Hit Rate vs held-out items
   - Tests cold-start: users with <3 reviews in training set
   - Outputs a formatted table + saves eval_results_task_b.json

3. Finalize both Dockerfiles:
   - Multi-stage builds (builder + runtime)
   - Non-root user
   - Health check instructions
   - .dockerignore files

4. Finalize docker-compose.yml:
   - task_a service (port 8001)
   - task_b service (port 8002)  
   - chromadb service (port 8000) using chromadb/chroma docker image
   - Shared volumes: ./data, ./chroma_data
   - Environment: reads from .env file
   - depends_on with health checks

5. Write README.md (this is what judges see first):
   - Quick start (3 commands: git clone, cp .env.example .env, 
     docker-compose up)
   - Architecture diagram (ASCII)
   - API documentation (endpoint descriptions + curl examples)
   - Dataset setup instructions (where to download, where to place)
   - Evaluation instructions
   - Design decisions section (why ChromaDB, why this agent loop, etc.)
   - Known limitations and future work

<constraints>
- docker-compose up should work end-to-end with zero manual steps 
  (after datasets are placed in ./data)
- README curl examples must be copy-pasteable and actually work
- Include a Makefile with targets: build, up, down, eval-a, eval-b, ingest
</constraints>