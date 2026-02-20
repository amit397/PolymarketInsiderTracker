"""FastAPI application entry point."""

from __future__ import annotations

import logging
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.database import init_db
from app.services.scan_loop import scan_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Startup / shutdown lifecycle."""
    await init_db()
    logging.getLogger(__name__).info("Database initialised")
    
    # Debug log to verify execution reach
    logging.getLogger(__name__).info("Attempting to start scan_loop...")
    scan_loop.start()
    logging.getLogger(__name__).info("scan_loop.start() called")
    
    yield
    await scan_loop.stop()


app = FastAPI(
    title="Polymarket Insider Trading Tracker",
    description="Detects suspicious trading activity on Polymarket",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS – allow the Next.js frontend in dev + production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://polymarketinsider.vercel.app",
        "https://polymarketinsider-*-amitzxc123-6796s-projects.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}
