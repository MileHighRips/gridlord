"""GridironIQ FastAPI application entrypoint.

Run:  uvicorn main:app --reload
Docs: http://localhost:8000/docs
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import (
    auth,
    board,
    draft,
    leagues,
    lineup,
    news,
    players,
    projections,
    sources,
    sync,
    trades,
    waivers,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="GridironIQ API",
    version="1.0.0",
    description="Championship-grade fantasy football analytics & cross-platform sync.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (
    auth, leagues, players, projections, draft, lineup, waivers, trades, sync,
    news, sources, board,
):
    app.include_router(r.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "service": "gridiron-iq"}
