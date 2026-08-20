"""Cross-platform sync endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditLog
from ..providers import PROVIDERS, get_provider

router = APIRouter(prefix="/api/sync", tags=["sync"])


class SyncRequest(BaseModel):
    provider: str
    league_id: str


@router.get("/providers")
def list_providers() -> dict:
    return {"providers": PROVIDERS, "write_capable": ["yahoo"]}


@router.post("/league")
def sync_league(req: SyncRequest, db: Session = Depends(get_db)) -> dict:
    """Fetch league metadata + settings from a provider (read-only)."""
    try:
        data = get_provider(req.provider).fetch_league(req.league_id)
    except Exception as exc:  # noqa: BLE001 - surface provider errors to client
        raise HTTPException(502, f"Provider error: {exc}") from exc
    db.add(
        AuditLog(
            action="sync", sources=req.provider, league_id=None,
            detail_json=f'{{"league_id": "{req.league_id}"}}',
        )
    )
    db.commit()
    return data


@router.post("/roster")
def sync_roster(req: SyncRequest) -> dict:
    try:
        roster = get_provider(req.provider).fetch_roster(req.league_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Provider error: {exc}") from exc
    return {"league_id": roster.league_id, "teams": roster.teams}


@router.post("/transactions")
def sync_transactions(req: SyncRequest) -> dict:
    try:
        txns = get_provider(req.provider).fetch_transactions(req.league_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Provider error: {exc}") from exc
    return {"count": len(txns), "transactions": txns[:50]}
