"""Player schemas."""
from __future__ import annotations

from pydantic import BaseModel


class PlayerOut(BaseModel):
    id: int
    name: str
    position: str
    team: str | None = None
    bye_week: int | None = None
    injury_status: str | None = None
    play_probability: float | None = None

    model_config = {"from_attributes": True}
