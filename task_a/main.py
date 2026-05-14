
"""FastAPI entrypoint for Task A: user modeling and review generation."""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv(override=True)

import logging
from os import getenv

from fastapi import FastAPI

from task_a.agent import UserModelingAgent
from task_a.schemas import HealthResponse, ReviewRequest, ReviewResponse

log_level_name = getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_name, logging.INFO)

root_logger = logging.getLogger()
if not root_logger.handlers:
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s: %(name)s: %(message)s",
    )
else:
    root_logger.setLevel(log_level)

for logger_name in [
    "task_a",
    "shared",
    "task_a.agent",
    "task_a.review_generator",
    "shared.vector_store",
    "shared.nigerian_adapter",
    "shared.llm_client",
]:
    logging.getLogger(logger_name).setLevel(log_level)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Task A - User Modeling Service",
    description=(
        "Generates a user-aligned review, star rating, confidence score, and style notes "
        "from persona history and item details."
    ),
    version="0.2.0",
)

agent = UserModelingAgent()
logger.info("Task A logging initialized at level %s", log_level_name)


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns the service health status for orchestration and monitoring.",
)
async def health() -> HealthResponse:
    """Returns a simple health response for container orchestration."""
    return HealthResponse(status="ok", service="task_a")


@app.post(
    "/generate-review",
    response_model=ReviewResponse,
    summary="Generate a simulated review",
    description=(
        "Produces a user-specific review, predicted rating, confidence score, and style notes "
        "using persona analysis, few-shot retrieval, and Claude-backed generation."
    ),
)
async def generate_review(payload: ReviewRequest) -> ReviewResponse:
    """Runs the full Task A user modeling pipeline."""
    return await agent.run(payload)
