"""
anytool platform — API server.

One API key. Connect apps. Call tools. Deploy triggers.

    uvicorn server.main:app --port 8100

Or:
    python -m server.main
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from server.config import config
from server.database import init_db, list_records, update_record_fields
from server.engine import get_api, close_api
from server.trigger_engine import get_trigger_engine, stop_trigger_engine

_usage_reset_task = None


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

    # Start monthly usage reset background task
    global _usage_reset_task
    _usage_reset_task = asyncio.create_task(_monthly_usage_reset_loop())
    logger.info("✅ Usage reset scheduler started")

    logger.info("🎉 anytool platform ready")
    logger.info(f"   API: {config.base_url}{config.api_prefix}")
    logger.info(f"   Docs: {config.base_url}/docs")

    yield

    # Shutdown
    logger.info("🛑 Shutting down...")
    if _usage_reset_task:
        _usage_reset_task.cancel()
    await stop_trigger_engine()
    await close_api()
    logger.info("✅ Shutdown complete")


async def _monthly_usage_reset_loop():
    """Background task: reset calls_this_month on the 1st of each month."""
    while True:
        try:
            now = datetime.now(timezone.utc)
            # Check every hour
            await asyncio.sleep(3600)

            now = datetime.now(timezone.utc)
            if now.day == 1 and now.hour == 0:
                workspaces = await list_records("workspace")
                reset_count = 0
                for ws in workspaces:
                    data = ws.custom_data or {}
                    last_reset = data.get("last_usage_reset_month")
                    current_month = now.strftime("%Y-%m")

                    if last_reset != current_month:
                        await update_record_fields("workspace", ws.primary_field_value, {
                            "calls_this_month": 0,
                            "last_usage_reset_month": current_month,
                        })
                        reset_count += 1

                if reset_count:
                    logger.info(f"🔄 Monthly usage reset: {reset_count} workspaces")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Usage reset error: {e}")
            await asyncio.sleep(60)


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

from server.routers import accounts, connections, execute, triggers, dashboard

app.include_router(accounts.router, prefix=config.api_prefix)
app.include_router(connections.router, prefix=config.api_prefix)
app.include_router(execute.router, prefix=config.api_prefix)
app.include_router(triggers.router, prefix=config.api_prefix)
app.include_router(dashboard.router, prefix=config.api_prefix)


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
