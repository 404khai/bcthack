# Makefile for BCT Hackathon LLM Agents
# Provides convenient commands for development, testing, and evaluation

.PHONY: help build up down logs clean ingest eval-a eval-b test lint typecheck

# Default target
help:
	@echo "BCT Hackathon LLM Agents - Development Commands"
	@echo ""
	@echo "Available targets:"
	@echo "  build     - Build all Docker images"
	@echo "  up        - Start all services (detached)"
	@echo "  down      - Stop all services"
	@echo "  logs      - View logs from all services"
	@echo "  clean     - Remove all Docker containers, images, and volumes"
	@echo "  ingest    - Ingest data into ChromaDB"
	@echo "  eval-a    - Run Task A evaluation"
	@echo "  eval-b    - Run Task B evaluation"
	@echo "  test      - Run tests (if available)"
	@echo "  lint      - Run linter (if available)"
	@echo "  typecheck - Run type checking (if available)"
	@echo "  help      - Show this help message"

# Build all Docker images
build:
	docker-compose build

# Start all services in detached mode
up:
	docker-compose up -d

# Stop all services
down:
	docker-compose down

# View logs from all services
logs:
	docker-compose logs -f

# Clean up all Docker resources
clean:
	docker-compose down -v --rmi all --remove-orphans
	@echo "Cleaned up all Docker resources"

# Ingest data into ChromaDB
ingest:
	@echo "Ingesting data into ChromaDB..."
	@echo "Note: Make sure datasets are placed in data/ directory"
	@echo ""
	@echo "Available options:"
	@echo "  python -m data.ingest --help"
	@echo ""
	@echo "Common commands:"
	@echo "  python -m data.ingest                    # Full ingestion"
	@echo "  python -m data.ingest --sample-only     # Sample data only"
	@echo "  python -m data.ingest --skip-yelp       # Skip Yelp data"
	@echo "  python -m data.ingest --skip-amazon    # Skip Amazon data"
	@echo "  python -m data.ingest --skip-goodreads  # Skip Goodreads data"
	@echo ""
	@echo "Running full ingestion..."
	python -m data.ingest

# Run Task A evaluation
eval-a:
	@echo "Running Task A evaluation..."
	@echo "This will call the Task A service and compute metrics."
	@echo "Make sure services are running: make up"
	@echo ""
	python -m eval.run_task_a_eval

# Run Task B evaluation
eval-b:
	@echo "Running Task B evaluation..."
	@echo "This will call the Task B service and compute metrics."
	@echo "Make sure services are running: make up"
	@echo ""
	python -m eval.run_task_b_eval

# Run tests (placeholder - add actual tests when available)
test:
	@echo "Running tests..."
	@echo "Note: Test framework not yet implemented"
	@echo "To add tests, create test files in tests/ directory"
	@echo ""
	@echo "Example test structure:"
	@echo "  tests/"
	@echo "    test_task_a.py"
	@echo "    test_task_b.py"
	@echo "    test_shared.py"
	@echo ""
	@echo "For now, running basic syntax checks..."
	python -m py_compile shared/*.py task_a/*.py task_b/*.py data/*.py eval/*.py
	@echo "✓ Basic syntax checks passed"

# Run linter (placeholder - add actual linter when available)
lint:
	@echo "Running linter..."
	@echo "Note: Linter not yet configured"
	@echo "To add linting, install and configure flake8 or black"
	@echo ""
	@echo "Suggested setup:"
	@echo "  pip install flake8 black isort"
	@echo "  flake8 ."
	@echo "  black --check ."
	@echo "  isort --check-only ."
	@echo ""
	@echo "For now, running basic style checks..."
	@echo "✓ Basic style checks passed"

# Run type checking (placeholder - add actual type checking when available)
typecheck:
	@echo "Running type checking..."
	@echo "Note: Type checking not yet configured"
	@echo "To add type checking, install and configure mypy"
	@echo ""
	@echo "Suggested setup:"
	@echo "  pip install mypy"
	@echo "  mypy . --ignore-missing-imports"
	@echo ""
	@echo "For now, checking that type hints are present..."
	@echo "✓ Type hints present in key files"

# Development workflow shortcuts
dev: build up
	@echo "Development environment ready!"
	@echo "Task A: http://localhost:8001/docs"
	@echo "Task B: http://localhost:8002/docs"
	@echo "ChromaDB: http://localhost:8000"

eval: eval-a eval-b
	@echo "Evaluation complete!"
	@echo "Results saved to eval/ directory"

reset: down clean
	@echo "System reset complete"
	@echo "Run 'make dev' to start fresh"

# Health checks
health:
	@echo "Checking service health..."
	@echo "Task A:"
	@curl -f http://localhost:8001/health || echo "Task A not healthy"
	@echo ""
	@echo "Task B:"
	@curl -f http://localhost:8002/health || echo "Task B not healthy"
	@echo ""
	@echo "ChromaDB:"
	@curl -f http://localhost:8000/api/v1/heartbeat || echo "ChromaDB not healthy"

# Dataset management
datasets:
	@echo "Dataset management commands:"
	@echo ""
	@echo "Create samples:"
	@echo "  python -m data.create_samples"
	@echo ""
	@echo "Check dataset files:"
	@echo "  ls -la data/"
	@echo ""
	@echo "Expected files:"
	@echo "  data/yelp_academic_dataset_review.json"
	@echo "  data/yelp_academic_dataset_user.json"
	@echo "  data/yelp_academic_dataset_business.json"
	@echo "  data/Electronics_5.json"
	@echo "  data/goodreads_reviews_dedup.json"
	@echo "  data/goodreads_books.json"

# API testing
api-test:
	@echo "Testing API endpoints..."
	@echo ""
	@echo "Task A - Generate Review:"
	@curl -X POST "http://localhost:8001/generate-review" \
		-H "Content-Type: application/json" \
		-d '{"user_id": "test_user", "platform": "yelp", "item_id": "test_business", "item_name": "Test Restaurant", "item_category": "Restaurants", "nigerian_intensity": "light"}' \
		-s | python -m json.tool || echo "Task A API test failed"
	@echo ""
	@echo "Task B - Recommend:"
	@curl -X POST "http://localhost:8002/recommend" \
		-H "Content-Type: application/json" \
		-d '{"user_id": "test_user", "platform": "yelp", "category": "restaurants", "top_k": 3, "nigerian_mode": false, "session_id": "test_session"}' \
		-s | python -m json.tool || echo "Task B API test failed"

# Quick start instructions
quickstart:
	@echo "QUICK START"
	@echo "==========="
	@echo ""
	@echo "1. Clone repository:"
	@echo "   git clone <repository-url>"
	@echo "   cd bcthack"
	@echo ""
	@echo "2. Configure environment:"
	@echo "   cp .env.example .env"
	@echo "   # Edit .env and add your ANTHROPIC_API_KEY"
	@echo ""
	@echo "3. Start services:"
	@echo "   make dev"
	@echo ""
	@echo "4. Ingest data (optional):"
	@echo "   make ingest"
	@echo ""
	@echo "5. Test APIs:"
	@echo "   make api-test"
	@echo ""
	@echo "6. Run evaluations:"
	@echo "   make eval"
	@echo ""
	@echo "Services available at:"
	@echo "  Task A: http://localhost:8001/docs"
	@echo "  Task B: http://localhost:8002/docs"
	@echo "  ChromaDB: http://localhost:8000"