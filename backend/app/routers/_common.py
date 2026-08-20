"""Shared helpers for routers: load ranked players from the DB."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..engine.league_context import build_league_context, default_starters_from_slots
from ..engine.rankings import PlayerProjection, RankedPlayer, rank_players
from ..models import ADPEntry, League, Player, Projection


def load_player_projections(
    db: Session, season: int = 2026, week: int = 0
) -> list[PlayerProjection]:
    """Join players + ensemble projections + ADP + intel into ranking inputs."""
    players = {p.id: p for p in db.query(Player).filter(Player.active).all()}
    adp = {a.player_id: a for a in db.query(ADPEntry).all()}
    projs = (
        db.query(Projection)
        .filter(Projection.season == season, Projection.week == week)
        .all()
    )
    out: list[PlayerProjection] = []
    for pr in projs:
        p = players.get(pr.player_id)
        if not p:
            continue
        out.append(
            PlayerProjection(
                player_id=p.id,
                name=p.name,
                position=p.position,
                team=p.team,
                proj_points=pr.mean_points,
                std_points=pr.std_points,
                adp=adp[p.id].adp if p.id in adp and adp[p.id].adp < 990 else None,
                last_year_points=p.last_year_points,
                injury_status=p.injury_status,
                play_probability=p.play_probability,
                ecr=p.ecr,
                ecr_std=p.ecr_std,
                ecr_delta=p.ecr_delta,
                boom_pct=pr.boom_pct,
                bust_pct=pr.bust_pct,
                consensus_rank=p.consensus_rank,
                usage_score=p.usage_score,
                role_note=p.role_note,
                volatility_index=p.volatility_index,
            )
        )
    return out


def _replacement_for_league(db: Session) -> dict[str, int] | None:
    """Build league-size-aware replacement ranks from the first league's roster."""
    league = db.query(League).first()
    if not league or not league.roster_slots:
        return None
    starters = default_starters_from_slots(league.roster_slots)
    ctx = build_league_context(league.num_teams, starters)
    return ctx.replacement_rank


def load_ranked_players(
    db: Session, season: int = 2026, week: int = 0
) -> list[RankedPlayer]:
    replacement = _replacement_for_league(db)
    return rank_players(load_player_projections(db, season, week), replacement)
