"""ORCA — Marine EcOsystem Reasoning with Collaborative Agents.

FastAPI application entry point.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("orca")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    logger.info(f"🌊 ORCA v{settings.APP_VERSION} starting up...")
    logger.info(f"Data mode: {settings.DATA_MODE}")

    # Initialize providers
    from data.providers import get_registry
    registry = get_registry()
    logger.info(f"Initialized {len(registry.providers)} data providers")

    # Initialize ML Engine & Warm up cache
    from ml.predictor import get_ml_engine
    from data.service import get_data_service
    get_ml_engine()
    await get_data_service().warm_up_cache()
    logger.info("⚡ ML Engine & Cache initialization complete.")

    yield

    logger.info("🌊 ORCA shutting down...")


app = FastAPI(
    title="ORCA — Marine Ecosystem Intelligence",
    description=(
        "Multi-agent marine ecosystem reasoning platform. "
        "Combines real environmental data with AI agent analysis "
        "to provide explainable ecosystem insights."
    ),
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS: Allow web apps, Capacitor mobile apps, and local network IPs
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"^(https?://.*|capacitor://.*)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
from api.query import router as query_router
from api.map import router as map_router
from api.sources import router as sources_router
from api.health import router as health_router
from api.conversation import router as conversation_router

app.include_router(query_router)
app.include_router(map_router)
app.include_router(sources_router)
app.include_router(health_router)
app.include_router(conversation_router)


@app.get("/health")
async def health_check():
    """Lightweight backend health check endpoint for quick connectivity verification."""
    return {
        "status": "ok",
        "service": "orca-backend",
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "ORCA — Marine EcOsystem Reasoning with Collaborative Agents",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
        "api_health": "/api/v1/health",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)

