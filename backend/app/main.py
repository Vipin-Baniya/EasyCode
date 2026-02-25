"""
Main FastAPI application for Project Core.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan – startup and shutdown hooks."""
    logger.info("🚀 Starting Project Core API  env={}", settings.environment)

    # Create workspace root if it doesn't exist
    import pathlib
    pathlib.Path(settings.workspace_root).mkdir(parents=True, exist_ok=True)

    yield

    logger.info("🛑 Shutting down Project Core API")


app = FastAPI(
    title="Project Core API",
    description="AI-powered, safe code-generation system",
    version="2.0.0",
    lifespan=lifespan,
    debug=settings.debug,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else settings.effective_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(router, prefix="/api/v1")


@app.get("/", tags=["meta"])
async def root() -> dict:
    return {"name": "Project Core API", "version": "2.0.0", "status": "running",
            "environment": settings.environment}


@app.get("/health", tags=["meta"])
async def health_check() -> dict:
    return {"status": "healthy", "environment": settings.environment}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        workers=1 if settings.api_reload else settings.api_workers,
    )
