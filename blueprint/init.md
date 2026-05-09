Phase 1 (Days 1–2):   Project scaffold, Docker, dataset pipeline C:\Users\DanielsFega\Hackathons\bcthack\blueprint\phase1.md
Phase 2 (Days 3–5):   Task A core — persona builder + review generator
Phase 3 (Days 6–9):   Task B core — reasoning agent + RAG recommender
Phase 4 (Days 10–11): Cold-start, cross-domain, multi-turn (Task B scoring)
Phase 5 (Day 12):     Nigerian contextualization layer
Phase 6 (Days 13–14): Evaluation harness, metrics, README
Phase 7 (Day 15):     Solution paper draft (4–8 pages)

1. What You're Actually Building
Two containerized LLM-powered microservices:
Task A — User Modeling
Input: User persona + item/product details
Output: Simulated star rating + written review
Core challenge: Behavioral mimicry + style fidelity
Secret weapon: Nigerian linguistic contextualization

Task B — Recommendation
Input: User persona (cold or warm) + item/product details
Output: Ranked list of personalized recommendations
Core challenge: Reasoning-first retrieval + cold-start handling
Secret weapon: Multi-turn conversation + cross-domain reasoning

2. Architecture Overview
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

3. Tech Stack (Chosen for Score Maximization)

Framework: FastAPI (async, clean API docs, easy containerization)
LLM Backbone: Claude API via anthropic SDK (or swap to OpenAI) — prompt-driven, no fine-tuning needed
Embeddings: sentence-transformers/all-MiniLM-L6-v2 (fast, free, local)
Vector Store: ChromaDB (persistent, no external server, Docker-friendly)
Agent Orchestration: LangChain (chains + agents) or hand-rolled (cleaner for paper)
Dataset Handling: datasets (HuggingFace) + pandas
Containerization: Docker + docker-compose
Evaluation: rouge-score, bert-score, scikit-learn (RMSE)

4. Dataset Strategy 
Yelp Open Dataset       → Task A (restaurants/businesses, rich reviews)
                        → Task B (local recommendations, cold-start)

Amazon Reviews (McAuley) → Task A (product reviews, rating patterns)
                         → Task B (cross-domain: books→products)

Goodreads (UCSD)        → Task A (literary tone profiles)
                        → Task B (cross-domain: books→movies→food)

Practical data pipeline:
- Download subsets (don't use full datasets — 5–10k users is enough)
- Filter users with ≥10 reviews (behavioral signal richness)
- For each user: extract {reviews[], ratings[], categories[], writing_style_fingerprint}
- Store user profiles in ChromaDB with metadata
- Reserve 20% of each user's reviews as held-out test set for RMSE/ROUGE evaluation

5. Nigerian Contextualization (Bonus Marks — Don't Skip)
This is an explicit bonus signal. Implement a NigerianContextAdapter that:

Injects Naija food/place references (suya, jollof rice, Shoprite, Jumia)
Optionally generates Pidgin-inflected review tone ("this place dey burst my brain")
Maps Western product categories to Nigerian equivalents
Applies as a toggle (switchable for eval vs. demo)

Quick-Reference Checklist Before Submission
Deliverable 1 — Task A endpoint:    POST http://your-host:8001/generate-review
Deliverable 1 — Task B endpoint:    POST http://your-host:8002/recommend
Deliverable 2 — Solution paper:     4–8 pages, architecture + ablation studies
Deliverable 3 — GitHub repo:        clean README, modular, well-commented

Score maximizers:
  ✓ "thinking" field in Task B response (judges see reasoning)
  ✓ explanation field on every recommendation (contextual relevance)
  ✓ nigerian_mode toggle on both tasks (bonus marks)
  ✓ cold-start works with empty history (25 pts)
  ✓ cross-domain example in README (Goodreads → food recommendation)
  ✓ solution paper written like you're explaining to a tech lead, not a jury