"""Waiver / FAAB recommendation endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..engine.waivers import WaiverCandidate, recommend_waivers
from ..models import ADPEntry, Player, Projection
from ._common import load_ranked_players

router = APIRouter(prefix="/api/waivers", tags=["waivers"])


class WaiverRequest(BaseModel):
    faab_budget: int = 100
    faab_remaining: int = 100
    my_needs: list[str] = []
    rostered_cutoff: float = 0.7  # only suggest players rostered below this %


@router.post("/recommend")
def waivers(req: WaiverRequest, db: Session = Depends(get_db)) -> list[dict]:
    ranked = {r.player_id: r for r in load_ranked_players(db)}
    players = {p.id: p for p in db.query(Player).filter(Player.active).all()}
    adp = {a.player_id: a for a in db.query(ADPEntry).all()}
    projs = db.query(Projection).filter(Projection.week == 0).all()

    candidates: list[WaiverCandidate] = []
    for pr in projs:
        p = players.get(pr.player_id)
        r = ranked.get(pr.player_id)
        if not p or not r:
            continue
        a = adp.get(p.id)
        rostered = a.rostered_pct if a and a.rostered_pct is not None else 0.1
        if rostered > req.rostered_cutoff:
            continue
        candidates.append(
            WaiverCandidate(
                player_id=p.id, name=p.name, position=p.position,
                proj_points_next=round(pr.mean_points / 17, 1),
                ros_points=pr.mean_points, vorp=r.vorp,
                rostered_pct=rostered, trend_factor=1.08,
            )
        )
    return recommend_waivers(candidates, req.faab_budget, req.faab_remaining, req.my_needs)
