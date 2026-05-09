
"""FastAPI entrypoint for Task A: user modeling and review generation."""

from __future__ import annotations

from fastapi import FastAPI

from task_a.agent import UserModelingAgent
from task_a.schemas import HealthResponse, ReviewRequest, ReviewResponse

app = FastAPI(
    title="Task A - User Modeling Service",
    description=(
        "Generates a user-aligned review, star rating, confidence score, and style notes "
        "from persona history and item details."
    ),
    version="0.2.0",
)

agent = UserModelingAgent()


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
