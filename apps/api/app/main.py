"""BiliBookLLM API — FastAPI application entry point."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.exceptions import ResponseValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import engine, Base
from app.routers import jobs, export

# Configure structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if settings.debug else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        structlog.get_config()["wrapper_class"].log_level if not settings.debug else 0
    ),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown hooks."""
    logger.info("starting_up", debug=settings.debug)

    # Ensure data and temp directories exist
    settings.data_path
    settings.temp_path

    # Create database tables (for SQLite — in production use Alembic)
    async with engine.begin() as conn:
        # Import models so they register with Base
        from app.models import Job, Transcript, TranscriptSegment, SummaryResult  # noqa: F401

        await conn.run_sync(Base.metadata.create_all)

    logger.info("database_ready", url=settings.database_url)

    yield

    # Shutdown
    await engine.dispose()
    logger.info("shutdown_complete")


# ── App Factory ─────────────────────────────────────────────────

app = FastAPI(
    title="BiliBookLLM API",
    description="Turn Bilibili videos into structured notes",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.exception_handler(ResponseValidationError)
async def response_validation_exception_handler(request, exc: ResponseValidationError):
    """Return JSON instead of Starlette’s plain “Internal Server Error” on response model mismatch."""
    logger.error("response_validation_failed", path=str(request.url.path), err=str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "error": {
                    "code": "RESPONSE_VALIDATION_ERROR",
                    "message": str(exc)[:2000],
                }
            }
        },
    )


# CORS: list env origins + dev regex (任意端口、局域网 IP、::1 打开前端时仍可直接调 API，避免 “Failed to fetch”)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|\[::1\]|192\.168\.\d{1,3}\.\d{1,3})(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(jobs.router)
app.include_router(export.router)


# ── Health Check ────────────────────────────────────────────────


@app.get("/health", tags=["system"])
async def health_check():
    """Health check endpoint."""
    # Check if whisper model is loaded
    whisper_loaded = False
    try:
        from app.modules.transcriber import _whisper_model

        whisper_loaded = _whisper_model is not None
    except Exception:
        pass

    return {
        "status": "ok",
        "version": "0.1.0",
        "whisper_model_loaded": whisper_loaded,
    }
