"""News feed endpoints (aggregated RSS with injury/role tags)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import NewsItem, Player

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("")
def list_news(
    tag: str | None = Query(None, description="injury | role_change | news"),
    limit: int = 60,
    db: Session = Depends(get_db),
) -> list[dict]:
    q = db.query(NewsItem).order_by(NewsItem.published_at.desc())
    if tag:
        q = q.filter(NewsItem.tags.ilike(f"%{tag}%"))
    items = q.limit(limit).all()
    player_names = {
        p.id: p.name
        for p in db.query(Player).filter(
            Player.id.in_([i.player_id for i in items if i.player_id])
        )
    }
    return [
        {
            "id": i.id,
            "headline": i.headline,
            "summary": i.summary,
            "url": i.url,
            "source": i.source,
            "tags": (i.tags or "").split(","),
            "player_id": i.player_id,
            "player_name": player_names.get(i.player_id),
            "published_at": i.published_at.isoformat() if i.published_at else None,
        }
        for i in items
    ]


@router.get("/injuries")
def injury_report(db: Session = Depends(get_db)) -> list[dict]:
    """Players currently carrying an injury designation (drives ranking discounts)."""
    players = (
        db.query(Player)
        .filter(Player.injury_status.isnot(None), Player.active)
        .order_by(Player.position)
        .all()
    )
    return [
        {
            "player_id": p.id,
            "name": p.name,
            "position": p.position,
            "team": p.team,
            "injury_status": p.injury_status,
            "note": p.injury_note,
            "play_probability": p.play_probability,
        }
        for p in players
        if p.injury_status
    ]
