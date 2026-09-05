"""Integration test: import a sample league JSON, then run a ranking refresh.

Uses a throwaway SQLite DB configured before the app is imported.
"""
from __future__ import annotations

import os

os.environ["DATABASE_URL"] = "sqlite:///./test_integration.db"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def _safe_remove(path: str) -> None:
    """Best-effort delete; SQLite may briefly hold the file on Windows."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except PermissionError:
        pass


@pytest.fixture(scope="module")
def client():
    # Fresh DB file per run.
    _safe_remove("test_integration.db")
    from app.database import engine  # imported after DATABASE_URL is set
    from main import app

    with TestClient(app) as c:
        yield c

    # Release the SQLite file handle before attempting cleanup.
    engine.dispose()
    _safe_remove("test_integration.db")


SAMPLE_SLEEPER_LEAGUE = {
    "leagueName": "Import Test PPR",
    "teams": 12,
    "season": 2026,
    "scoring": {
        "type": "PPR",
        "rules": {
            "pass_yd": 0.04,
            "pass_td": 4,
            "pass_int": -4,
            "rush_yd": 0.1,
            "rush_td": 6,
            "rec": 1.0,
            "rec_yd": 0.1,
            "rec_td": 6,
            "fum_lost": -2,
        },
    },
    "roster": {
        "starters": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "DEF": 1},
        "bench": 6,
        "ir_slots": 2,
    },
}


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_default_league_endpoint(client):
    data = client.get("/api/leagues/defaults").json()
    assert data["teams"] == 10
    assert data["scoring"]["type"] == "PPR"


def test_import_league_maps_over_90pct(client):
    resp = client.post(
        "/api/leagues/import",
        json={"provider": "sleeper", "leagueSettingsJson": SAMPLE_SLEEPER_LEAGUE},
    )
    assert resp.status_code == 200
    body = resp.json()
    # Acceptance criterion: >90% field mapping accuracy.
    assert body["mapping_accuracy"] >= 0.9
    assert body["league"]["scoring_type"] == "PPR"
    assert body["league"]["settings"]["roster"]["starters"]["RB"] == 2


def test_ranking_refresh_after_seed(client):
    # Seed players so rankings have data.
    from app.seed import seed

    seed()
    refresh = client.post("/api/projections/refresh").json()
    assert refresh["status"] == "ok"
    assert refresh["players_ranked"] > 0

    rankings = client.get("/api/projections/rankings?limit=25").json()
    assert len(rankings) > 0
    assert rankings[0]["rank"] == 1
    assert len(rankings[0]["drivers"]) >= 1


def test_refresh_live_retries_transient_sqlite_lock(monkeypatch):
    """A brief SQLite lock should be retried instead of surfacing a hard 500."""
    import sqlite3

    from app.routers import projections

    calls = {"count": 0}

    def fake_ingest():
        calls["count"] += 1
        if calls["count"] == 1:
            raise sqlite3.OperationalError("database is locked")
        return {"players": 12, "news": 2, "live_players": 12, "live_news": 2,
                "ecr_matched": 0, "buzz_matched": 0, "reason": None, "errors": [], "elapsed_seconds": 0.1}

    monkeypatch.setattr("app.ingest.run_ingest", fake_ingest)
    monkeypatch.setattr(projections.time, "sleep", lambda *_args, **_kwargs: None)

    result = projections._run_refresh_with_retry()
    assert result["players"] == 12
    assert calls["count"] == 2


def test_live_draft_recommendation(client):
    from app.seed import seed

    seed()
    state = {
        "league_id": 1,
        "num_teams": 14,
        "rounds": 16,
        "my_slot": 7,
        "draft_type": "snake",
        "picks_made": [],
    }
    resp = client.post("/api/draft/recommend", json=state).json()
    assert "recommendations" in resp
    assert resp["your_next_overall_pick"] == 7
    assert len(resp["recommendations"]) > 0
