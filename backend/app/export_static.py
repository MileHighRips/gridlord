"""Export a static data snapshot for the GitHub Pages (serverless) build.

Writes JSON the frontend can read directly when no backend API is available, so
the deployed PWA shows real, daily-refreshed data. The heavy lifting (rankings,
hidden gems, live-draft recs, scoring re-score) runs client-side from
``players.json`` — which includes each player's raw stat line — so the app stays
fully interactive on a phone with no server.

Run:  python -m app.export_static [output_dir]
Default output: ../frontend/public/data
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

from .database import SessionLocal
from .defaults import DEFAULT_LEAGUE
from .engine.montecarlo import TeamSeasonInput, simulate_season
from .models import ADPEntry, League, NewsItem, Player, Projection, Team
from .routers._common import load_ranked_players
from .services import league_to_settings


def _players_payload(db) -> list[dict]:
    players = {p.id: p for p in db.query(Player).filter(Player.active).all()}
    adp = {a.player_id: a for a in db.query(ADPEntry).all()}
    projs = db.query(Projection).filter(Projection.week == 0).all()
    out = []
    for pr in projs:
        p = players.get(pr.player_id)
        if not p:
            continue
        a = adp.get(p.id)
        raw = {}
        if pr.raw_stats_json:
            try:
                raw = json.loads(pr.raw_stats_json)
            except (ValueError, TypeError):
                raw = {}
        out.append(
            {
                "player_id": p.id,
                "name": p.name,
                "position": p.position,
                "team": p.team,
                "bye_week": p.bye_week,
                "ecr": p.ecr,
                "ecr_delta": p.ecr_delta,
                "adp": (a.adp if a and a.adp is not None and a.adp < 990 else None),
                "rostered_pct": (a.rostered_pct if a else None),
                "injury_status": p.injury_status,
                "play_probability": p.play_probability,
                "last_year_points": p.last_year_points,
                "usage_score": p.usage_score,
                "role_note": p.role_note,
                "volatility_index": p.volatility_index,
                "practice_status": p.practice_status,
                "raw_stats": raw,
            }
        )
    return out


def _news_payload(db) -> list[dict]:
    players = {p.id: p.name for p in db.query(Player).all()}
    items = (
        db.query(NewsItem).order_by(NewsItem.published_at.desc()).limit(200).all()
    )
    return [
        {
            "id": i.id,
            "headline": i.headline,
            "summary": i.summary,
            "url": i.url,
            "source": i.source,
            "tags": (i.tags or "").split(","),
            "player_id": i.player_id,
            "player_name": players.get(i.player_id),
            "published_at": i.published_at.isoformat() if i.published_at else None,
        }
        for i in items
    ]


def _injuries_payload(db) -> list[dict]:
    rows = (
        db.query(Player)
        .filter(Player.injury_status.isnot(None), Player.active)
        .all()
    )
    return [
        {
            "player_id": p.id, "name": p.name, "position": p.position, "team": p.team,
            "injury_status": p.injury_status, "note": p.injury_note,
            "play_probability": p.play_probability,
        }
        for p in rows
        if p.injury_status
    ]


def _sim_payload(db) -> dict:
    teams = db.query(Team).all()
    ranked = load_ranked_players(db)
    league_avg = (
        sum(r.proj_points for r in ranked[:14]) / 14 / 17 if ranked else 110
    )
    inputs = [
        TeamSeasonInput(
            team_id=t.id, name=t.name,
            weekly_mean=league_avg * (1.0 + (0.06 - 0.012 * i)),
            weekly_std=league_avg * 0.18,
        )
        for i, t in enumerate(teams)
    ]
    results = simulate_season(inputs, regular_weeks=14, playoff_teams=6, n_sims=5000)
    return {
        "n_sims": 5000,
        "standings": [
            {"team": r.name, "expected_wins": r.expected_wins,
             "playoff_prob": r.playoff_prob, "championship_prob": r.championship_prob,
             "avg_points": r.avg_points}
            for r in results
        ],
    }


def export(output_dir: str) -> dict:
    os.makedirs(output_dir, exist_ok=True)
    db = SessionLocal()
    try:
        league = db.query(League).first()
        settings = league_to_settings(league) if league else DEFAULT_LEAGUE

        files = {
            "players.json": _players_payload(db),
            "defaults.json": settings.model_dump(),
            "news.json": _news_payload(db),
            "injuries.json": _injuries_payload(db),
            "sim.json": _sim_payload(db),
            "meta.json": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "season": 2026,
            },
        }
        for name, payload in files.items():
            with open(os.path.join(output_dir, name), "w", encoding="utf-8") as fh:
                json.dump(payload, fh, separators=(",", ":"))
        counts = {k: (len(v) if isinstance(v, list) else 1) for k, v in files.items()}
        return counts
    finally:
        db.close()


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    default_out = os.path.normpath(
        os.path.join(here, "..", "..", "frontend", "public", "data")
    )
    out = sys.argv[1] if len(sys.argv) > 1 else default_out
    result = export(out)
    print(f"Exported static snapshot to {out}: {result}")
