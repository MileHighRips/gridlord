"""Data source status — which ranking/news providers are live vs need credentials."""
from __future__ import annotations

from fastapi import APIRouter

from ..sources import all_source_status

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("")
def sources() -> dict:
    rows = all_source_status()
    live = [r for r in rows if r["available"]]
    pending = [r for r in rows if not r["available"]]
    return {
        "live_count": len(live),
        "pending_count": len(pending),
        "sources": rows,
    }
