"""FastAPI entrypoint for Task A: user modeling and review generation."""

from __future__ import annotations

from fastapi import FastAPI

from task_a.agent import UserModelingAgent
from task_a.schemas import GenerateReviewRequest, GenerateReviewResponse, HealthResponse

app = FastAPI(
    title="Task A - User Modeling Service",
    description=(
        "Generates simulated user reviews and star ratings from persona history and item details."
    ),
    version="0.1.0",
)

agent = UserModelingAgent()


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns the service health status for orchestration and monitoring.",
)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="task_a")


@app.post(
    "/generate-review",
    response_model=GenerateReviewResponse,
    summary="Generate a simulated review",
    description=(
        "Produces a review and predicted rating that mimic the user's historical tone, "
        "preferences, and rating behavior."
    ),
)
async def generate_review(payload: GenerateReviewRequest) -> GenerateReviewResponse:
    return await agent.generate_review(payload)
