"""Custom draft board: personal ranking overrides per user."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_optional_user
from ..database import get_db
from ..models import CustomBoard, Player, User
from ._common import load_ranked_players

router = APIRouter(prefix="/api/board", tags=["board"])


class BoardIn(BaseModel):
    player_ids: list[int]
    name: str = "My Board"


def _board_for(db: Session, user: User | None) -> CustomBoard | None:
    uid = user.id if user else None
    return db.query(CustomBoard).filter(CustomBoard.user_id == uid).first()


@router.get("")
def get_board(
    db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)
) -> dict:
    """Return the saved board, or a starter board seeded from consensus rankings."""
    board = _board_for(db, user)
    if board:
        ids = json.loads(board.player_ids_json)
    else:
        ids = [r.player_id for r in load_ranked_players(db)[:200]]
    players = {p.id: p for p in db.query(Player).filter(Player.id.in_(ids)).all()}
    ordered = [
        {
            "player_id": pid,
            "name": players[pid].name,
            "position": players[pid].position,
            "team": players[pid].team,
        }
        for pid in ids
        if pid in players
    ]
    return {"saved": board is not None, "players": ordered}


@router.put("")
def save_board(
    body: BoardIn,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> dict:
    """Save the user's ordered custom board (guest boards are keyed to null user)."""
    board = _board_for(db, user)
    if not board:
        board = CustomBoard(user_id=user.id if user else None)
        db.add(board)
    board.name = body.name
    board.player_ids_json = json.dumps(body.player_ids)
    db.commit()
    return {"status": "ok", "count": len(body.player_ids)}
