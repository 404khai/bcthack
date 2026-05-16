
"""FastAPI entrypoint for Task A: user modeling and review generation."""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv(override=True)

import logging
import sys
from os import getenv

from fastapi import FastAPI

from task_a.agent import UserModelingAgent
from task_a.schemas import HealthResponse, ReviewRequest, ReviewResponse

log_level_name = getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_name, logging.INFO)
app_logger_names = [
    "task_a",
    "shared",
    "task_a.agent",
    "task_a.review_generator",
    "task_a.rating_predictor",
    "shared.vector_store",
    "shared.nigerian_adapter",
    "shared.llm_client",
]
LOG_FORMAT = "%(levelname)s: %(name)s: %(message)s"

root_logger = logging.getLogger()
if not root_logger.handlers:
    logging.basicConfig(
        level=log_level,
        format=LOG_FORMAT,
    )
else:
    root_logger.setLevel(log_level)

logger = logging.getLogger(__name__)
_app_handler: logging.Handler | None = None


def _get_app_handler() -> logging.Handler:
    """Creates a stable stdout handler for app logs across Uvicorn reloads."""
    global _app_handler
    if _app_handler is None:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        _app_handler = handler
    return _app_handler


def configure_app_logging() -> None:
    """Binds app loggers to an explicit stdout handler so request logs are always visible."""
    app_handler = _get_app_handler()

    for logger_name in app_logger_names:
        app_logger = logging.getLogger(logger_name)
        app_logger.handlers = [app_handler]
        app_logger.setLevel(log_level)
        app_logger.propagate = False

    logger.handlers = [app_handler]
    logger.setLevel(log_level)
    logger.propagate = False

app = FastAPI(
    title="Task A - User Modeling Service",
    description=(
        "Generates a user-aligned review, star rating, confidence score, and style notes "
        "from persona history and item details."
    ),
    version="0.2.0",
)

configure_app_logging()
agent = UserModelingAgent()
logger.info("Task A logging initialized at level %s", log_level_name)


@app.on_event("startup")
async def configure_logging_on_startup() -> None:
    """Re-applies logger handlers after Uvicorn startup to survive reload setups."""
    configure_app_logging()
    logger.info("Task A request logging is active")


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
    logger.info("Received /generate-review request for user_id=%s", payload.user_persona.user_id)
    response = await agent.run(payload)
    logger.info("Completed /generate-review request for user_id=%s", payload.user_persona.user_id)
    return response
