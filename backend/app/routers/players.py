"""Player endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ADPEntry, NewsItem, Player, Projection
from ..schemas.player import PlayerOut

router = APIRouter(prefix="/api/players", tags=["players"])


@router.get("", response_model=list[PlayerOut])
def list_players(
    position: str | None = Query(None),
    q: str | None = Query(None, description="Name search"),
    limit: int = 200,
    db: Session = Depends(get_db),
) -> list[PlayerOut]:
    query = db.query(Player).filter(Player.active)
    if position:
        query = query.filter(Player.position == position.upper())
    if q:
        query = query.filter(Player.name.ilike(f"%{q}%"))
    return query.limit(limit).all()


@router.get("/intel/board")
def intel_board(
    sort: str = Query("usage", description="usage | risers | boom | bust"),
    limit: int = 40,
    db: Session = Depends(get_db),
) -> list[dict]:
    """Advanced player intelligence: usage/buzz, role changes, boom/bust, ECR moves."""
    players = {p.id: p for p in db.query(Player).filter(Player.active).all()}
    projs = {
        pr.player_id: pr
        for pr in db.query(Projection).filter(Projection.week == 0).all()
    }
    rows = []
    for pid, p in players.items():
        pr = projs.get(pid)
        rows.append(
            {
                "player_id": p.id,
                "name": p.name,
                "position": p.position,
                "team": p.team,
                "usage_score": p.usage_score,
                "role_note": p.role_note,
                "volatility_index": p.volatility_index,
                "ecr": p.ecr,
                "ecr_delta": p.ecr_delta,
                "practice_status": p.practice_status,
                "injury_status": p.injury_status,
                "boom_pct": pr.boom_pct if pr else None,
                "bust_pct": pr.bust_pct if pr else None,
                "proj_points": pr.mean_points if pr else None,
            }
        )

    def key(r: dict) -> float:
        if sort == "risers":
            return r["ecr_delta"] or -999
        if sort == "boom":
            return r["boom_pct"] or 0
        if sort == "bust":
            return r["bust_pct"] or 0
        return r["usage_score"] or 0

    rows = [r for r in rows if key(r) not in (None, 0) or sort == "usage"]
    rows.sort(key=key, reverse=True)
    return rows[:limit]


@router.get("/{player_id}")
def get_player(player_id: int, db: Session = Depends(get_db)) -> dict:
    p = db.get(Player, player_id)
    if not p:
        raise HTTPException(404, "Player not found")
    proj = (
        db.query(Projection)
        .filter(Projection.player_id == player_id, Projection.week == 0)
        .first()
    )
    adp = db.query(ADPEntry).filter(ADPEntry.player_id == player_id).first()
    news = (
        db.query(NewsItem)
        .filter(NewsItem.player_id == player_id)
        .order_by(NewsItem.published_at.desc())
        .limit(10)
        .all()
    )
    return {
        "player": PlayerOut.model_validate(p).model_dump(),
        "projection": {
            "mean_points": proj.mean_points if proj else None,
            "std_points": proj.std_points if proj else None,
            "floor_points": proj.floor_points if proj else None,
            "ceiling_points": proj.ceiling_points if proj else None,
        },
        "adp": {"adp": adp.adp, "rostered_pct": adp.rostered_pct} if adp else None,
        "news": [
            {
                "headline": n.headline, "tags": n.tags, "source": n.source,
                "published_at": n.published_at.isoformat(),
            }
            for n in news
        ],
    }
