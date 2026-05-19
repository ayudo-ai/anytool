"""
anytool platform — API server.

One API key. Connect apps. Call tools. Deploy triggers.

    uvicorn server.main:app --port 8100

Or:
    python -m server.main
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from server.config import config
from server.database import init_db
from server.engine import get_api, close_api
from server.trigger_engine import get_trigger_engine, stop_trigger_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown."""
    # Startup
    logger.info("🚀 anytool platform starting...")

    await init_db()
    logger.info("✅ Database ready")

    api = get_api()
    logger.info(f"✅ AnyTool SDK initialized | actions={len(api.list_actions())}")

    # Start trigger engine (loads existing triggers from DB, starts polling)
    try:
        await get_trigger_engine()
        logger.info("✅ Trigger engine started")
    except Exception as e:
        logger.warning(f"⚠️ Trigger engine not started: {e}")

    logger.info("🎉 anytool platform ready")
    logger.info(f"   API: {config.base_url}{config.api_prefix}")
    logger.info(f"   Docs: {config.base_url}/docs")

    yield

    # Shutdown
    logger.info("🛑 Shutting down...")
    await stop_trigger_engine()
    await close_api()
    logger.info("✅ Shutdown complete")


app = FastAPI(
    title="anytool",
    description="Agent-native API integration platform. One API key. Connect apps. Call tools. Deploy triggers.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ───────────────────────────────────────────────────────────

from server.routers import accounts, connections, execute, triggers

app.include_router(accounts.router, prefix=config.api_prefix)
app.include_router(connections.router, prefix=config.api_prefix)
app.include_router(execute.router, prefix=config.api_prefix)
app.include_router(triggers.router, prefix=config.api_prefix)


@app.get("/")
async def root():
    return {
        "name": "anytool",
        "version": "0.1.0",
        "description": "Agent-native API integration platform",
        "docs": f"{config.base_url}/docs",
        "endpoints": {
            "signup": f"POST {config.api_prefix}/accounts",
            "connect": f"POST {config.api_prefix}/connections",
            "execute": f"POST {config.api_prefix}/execute",
            "triggers": f"POST {config.api_prefix}/triggers",
            "actions": f"GET {config.api_prefix}/actions",
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── CLI entry point ──────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server.main:app",
        host=config.host,
        port=config.port,
        reload=True,
    )
