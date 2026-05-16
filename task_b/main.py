
"""FastAPI entrypoint for Task B: personalized recommendations."""

from dotenv import load_dotenv
load_dotenv(override=True)

import logging
import os

from fastapi import FastAPI

from task_b.agent import RecommendationAgent
from task_b.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    RecommendRequest,
    RecommendResponse,
    SessionClearResponse,
    SessionHistoryResponse,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Task B - Recommendation Service",
    description=(
        "Returns ranked recommendations with a reasoning-first retrieval loop, contextual explanations, "
        "and in-memory multi-turn session support."
    ),
    version="0.3.0",
)

agent = RecommendationAgent()


@app.on_event("startup")
async def log_startup_environment() -> None:
    """Logs the core runtime environment Task B depends on."""
    logger.info("CHROMA_PERSIST_DIR: %s", os.getenv("CHROMA_PERSIST_DIR"))
    logger.info(
        "GEMINI_API_KEY loaded: %s",
        "yes" if os.getenv("GEMINI_API_KEY") else "NO - MISSING",
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns the service health status for orchestration and monitoring.",
)
async def health() -> HealthResponse:
    """Returns a simple health response for container orchestration."""
    return HealthResponse(status="ok", service="task_b")


@app.post(
    "/recommend",
    response_model=RecommendResponse,
    summary="Get personalized recommendations",
    description=(
        "Runs a reasoning-first loop that thinks, plans, retrieves, reranks, and responds with "
        "ranked recommendations plus transparent thinking steps."
    ),
)
async def recommend(payload: RecommendRequest) -> RecommendResponse:
    """Runs the single-shot recommendation pipeline."""
    return await agent.recommend(payload)


@app.post(
    "/recommend/chat",
    response_model=ChatResponse,
    summary="Conversational recommendations",
    description=(
        "Handles a multi-turn recommendation exchange using in-memory session state and returns "
        "refined recommendations plus a chat-oriented assistant reply."
    ),
)
async def recommend_chat(payload: ChatRequest) -> ChatResponse:
    """Runs the conversational recommendation pipeline."""
    return await agent.chat(payload)


@app.get(
    "/recommend/session/{session_id}",
    response_model=SessionHistoryResponse,
    summary="Get session history",
    description="Returns the in-memory conversation history stored for a recommendation session.",
)
async def get_session_history(session_id: str) -> SessionHistoryResponse:
    """Returns stored conversation history for a session."""
    return await agent.get_session_history(session_id)


@app.delete(
    "/recommend/session/{session_id}",
    response_model=SessionClearResponse,
    summary="Clear session history",
    description="Deletes the in-memory conversation state associated with a recommendation session.",
)
async def clear_session(session_id: str) -> SessionClearResponse:
    """Clears the in-memory state for a recommendation session."""
    agent.clear_session(session_id)
    return SessionClearResponse(session_id=session_id, cleared=True)
