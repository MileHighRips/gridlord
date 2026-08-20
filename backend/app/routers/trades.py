"""Trade analyzer endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..engine.trade_analyzer import TradeAsset, TradeSide, analyze_trade
from ..models import Projection
from ._common import load_ranked_players

router = APIRouter(prefix="/api/trades", tags=["trades"])


class TradeRequest(BaseModel):
    team_a: str = "You"
    team_b: str = "Them"
    team_a_gives: list[int]  # player ids
    team_b_gives: list[int]
    team_a_needs: list[str] = []
    team_b_needs: list[str] = []


@router.post("/analyze")
def analyze(req: TradeRequest, db: Session = Depends(get_db)) -> dict:
    ranked = {r.player_id: r for r in load_ranked_players(db)}
    proj = {
        p.player_id: p for p in db.query(Projection).filter(Projection.week == 0).all()
    }

    def build(ids: list[int]) -> list[TradeAsset]:
        assets = []
        for pid in ids:
            r = ranked.get(pid)
            pr = proj.get(pid)
            if not r or not pr:
                raise HTTPException(404, f"Player {pid} not found or unprojected")
            assets.append(
                TradeAsset(
                    player_id=pid, name=r.name, position=r.position,
                    ros_points=pr.mean_points, std_points=pr.std_points, vorp=r.vorp,
                )
            )
        return assets

    side_a = TradeSide(team=req.team_a, gives=build(req.team_a_gives), needs=req.team_a_needs)
    side_b = TradeSide(team=req.team_b, gives=build(req.team_b_gives), needs=req.team_b_needs)
    return analyze_trade(side_a, side_b)
