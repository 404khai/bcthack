"""FastAPI entrypoint for Task B: personalized recommendations."""

from __future__ import annotations

from fastapi import FastAPI

from task_b.agent import RecommendationAgent
from task_b.schemas import HealthResponse, RecommendRequest, RecommendResponse

app = FastAPI(
    title="Task B - Recommendation Service",
    description=(
        "Returns ranked recommendations with lightweight reasoning traces and explanations."
    ),
    version="0.1.0",
)

agent = RecommendationAgent()


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns the service health status for orchestration and monitoring.",
)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="task_b")


@app.post(
    "/recommend",
    response_model=RecommendResponse,
    summary="Get personalized recommendations",
    description=(
        "Retrieves, expands, and ranks personalized recommendations using user preferences, "
        "query intent, and optional cross-domain reasoning."
    ),
)
async def recommend(payload: RecommendRequest) -> RecommendResponse:
    return await agent.recommend(payload)
