"""Projection & ranking endpoints, plus daily refresh + Monte Carlo."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..engine.hidden_gems import GemCandidate, find_hidden_gems
from ..engine.montecarlo import TeamSeasonInput, simulate_season
from ..models import ADPEntry, AuditLog, Player, Projection, Team
from ..schemas.projection import RankingRow
from ._common import load_ranked_players

router = APIRouter(prefix="/api/projections", tags=["projections"])


@router.get("/rankings", response_model=list[RankingRow])
def rankings(
    position: str | None = Query(None),
    limit: int = 200,
    db: Session = Depends(get_db),
) -> list[RankingRow]:
    """Explainable top-N rankings with VORP, tiers, and drivers."""
    ranked = load_ranked_players(db)
    if position:
        ranked = [r for r in ranked if r.position == position.upper()]
        for i, r in enumerate(ranked, start=1):
            r.rank = i
    return [
        RankingRow(
            rank=r.rank, player_id=r.player_id, name=r.name, position=r.position,
            team=r.team, proj_points=r.proj_points, vorp=r.vorp,
            positional_rank=r.positional_rank, adp=r.adp, adp_delta=r.adp_delta,
            volatility=r.volatility, upside_score=r.upside_score, tier=r.tier,
            drivers=r.drivers, ecr=r.ecr, ecr_delta=r.ecr_delta,
            boom_pct=r.boom_pct, bust_pct=r.bust_pct, consensus_rank=r.consensus_rank,
            adp_divergence=r.adp_divergence, usage_score=r.usage_score,
            role_note=r.role_note,
        )
        for r in ranked[:limit]
    ]


@router.post("/refresh")
def refresh_rankings(db: Session = Depends(get_db)) -> dict:
    """Trigger a ranking refresh and write an audit log entry.

    In production this enqueues a background job (see docs/OPERATIONS.md);
    here it recomputes synchronously from stored projections.
    """
    ranked = load_ranked_players(db)
    db.add(
        AuditLog(
            action="ranking_refresh", sources="stored projections",
            detail_json=f'{{"players_ranked": {len(ranked)}}}',
        )
    )
    db.commit()
    return {
        "status": "ok",
        "players_ranked": len(ranked),
        "top_player": ranked[0].name if ranked else None,
    }


@router.post("/refresh-live")
def refresh_live() -> dict:
    """Pull fresh live data (Sleeper 2026 projections, 2025 stats, ADP, trending,
    injuries, and RSS news) and rebuild the player universe + rankings.

    This is the "daily live data" refresh. Schedule it nightly (see
    docs/OPERATIONS.md) or trigger it from the dashboard Refresh button.
    """
    from fastapi import HTTPException

    from ..ingest import run_ingest

    try:
        result = run_ingest()
    except Exception as exc:  # noqa: BLE001 - surface the real reason to the client
        raise HTTPException(
            status_code=503,
            detail=f"Live refresh failed: {type(exc).__name__}: {exc}",
        ) from exc
    return {"status": "ok", **result}


@router.get("/hidden-gems")
def hidden_gems(db: Session = Depends(get_db)) -> list[dict]:
    """Undervalued players by projection-vs-ADP delta and low rostered %."""
    players = {p.id: p for p in db.query(Player).filter(Player.active).all()}
    adp = {a.player_id: a for a in db.query(ADPEntry).all()}
    projs = db.query(Projection).filter(Projection.week == 0).all()
    candidates = []
    for pr in projs:
        p = players.get(pr.player_id)
        if not p:
            continue
        a = adp.get(p.id)
        real_adp = a.adp if a and a.adp is not None and a.adp < 990 else None
        candidates.append(
            GemCandidate(
                player_id=p.id, name=p.name, position=p.position,
                proj_points=pr.mean_points,
                adp=real_adp,
                rostered_pct=(a.rostered_pct if a and a.rostered_pct is not None else 0.1),
                usage_trend=1.05,
            )
        )
    return find_hidden_gems(candidates, delta_threshold=8.0)


@router.post("/simulate-season")
def simulate(n_sims: int = 5000, db: Session = Depends(get_db)) -> dict:
    """Monte Carlo season sim across the league's teams (demo uses even rosters)."""
    teams = db.query(Team).all()
    ranked = load_ranked_players(db)
    league_avg_weekly = (
        sum(r.proj_points for r in ranked[:14]) / 14 / 17 if ranked else 110
    )
    inputs = []
    for i, t in enumerate(teams):
        inputs.append(
            TeamSeasonInput(
                team_id=t.id, name=t.name,
                weekly_mean=league_avg_weekly * (1.0 + (0.06 - 0.012 * i)),
                weekly_std=league_avg_weekly * 0.18,
            )
        )
    results = simulate_season(inputs, regular_weeks=14, playoff_teams=6, n_sims=n_sims)
    return {
        "n_sims": n_sims,
        "standings": [
            {
                "team": r.name, "expected_wins": r.expected_wins,
                "playoff_prob": r.playoff_prob,
                "championship_prob": r.championship_prob, "avg_points": r.avg_points,
            }
            for r in results
        ],
    }
