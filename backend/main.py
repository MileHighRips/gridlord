"""GridironIQ FastAPI application entrypoint.

Run:  uvicorn main:app --reload
Docs: http://localhost:8000/docs
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
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

    # Ensure the app has a usable player universe on first boot. This prevents a
    # freshly deployed Render service from starting with an empty DB and showing
    # an empty rankings table until a manual refresh is triggered.
    from sqlalchemy.orm import Session

    from app.database import SessionLocal
    from app.models import Player

    db: Session = SessionLocal()
    try:
        if db.query(Player).count() == 0:
            from app.seed import seed

            seed()
    finally:
        db.close()

    yield


app = FastAPI(
    title="GridironIQ API",
    version="1.0.0",
    description="Championship-grade fantasy football analytics & cross-platform sync.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
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
