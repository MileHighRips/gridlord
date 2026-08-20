"""Lineup optimizer endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..engine.lineup_optimizer import LineupPlayer, optimize_lineup
from ..models import Player, Projection

router = APIRouter(prefix="/api/lineup", tags=["lineup"])


class LineupRequest(BaseModel):
    player_ids: list[int]
    slots: list[str] = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "DEF"]
    week: int = 1


@router.post("/optimize")
def optimize(req: LineupRequest, db: Session = Depends(get_db)) -> dict:
    players = {
        p.id: p for p in db.query(Player).filter(Player.id.in_(req.player_ids)).all()
    }
    projs = {
        pr.player_id: pr
        for pr in db.query(Projection)
        .filter(Projection.player_id.in_(req.player_ids), Projection.week == 0)
        .all()
    }
    lineup_players = []
    for pid in req.player_ids:
        p = players.get(pid)
        pr = projs.get(pid)
        if not p:
            continue
        weekly = round((pr.mean_points / 17) if pr else 0.0, 2)
        lineup_players.append(
            LineupPlayer(player_id=p.id, name=p.name, position=p.position, proj_points=weekly)
        )
    return optimize_lineup(lineup_players, req.slots)
