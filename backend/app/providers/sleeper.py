"""Sleeper adapter — Sleeper has a clean public read API (no auth for reads)."""
from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import settings
from .base import FantasyProvider, NormalizedRoster


class SleeperProvider(FantasyProvider):
    name = "sleeper"

    def __init__(self, base: str | None = None) -> None:
        self.base = base or settings.sleeper_base
        self._client = httpx.Client(timeout=15.0)

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=0.5, max=8))
    def _get(self, path: str) -> Any:
        resp = self._client.get(f"{self.base}{path}")
        resp.raise_for_status()
        return resp.json()

    def fetch_league(self, league_id: str) -> dict[str, Any]:
        data = self._get(f"/league/{league_id}")
        scoring = data.get("scoring_settings", {}) or {}
        roster_positions = data.get("roster_positions", []) or []
        starters: dict[str, int] = {}
        bench = 0
        for pos in roster_positions:
            if pos == "BN":
                bench += 1
            elif pos in ("IR", "TAXI"):
                continue
            else:
                key = "FLEX" if pos in ("FLEX", "WRT", "REC_FLEX") else pos
                key = "SUPERFLEX" if pos in ("SUPER_FLEX", "QB_FLEX") else key
                starters[key] = starters.get(key, 0) + 1
        return {
            "provider": "sleeper",
            "provider_league_id": league_id,
            "leagueName": data.get("name", "Sleeper League"),
            "teams": data.get("total_rosters", 12),
            "season": int(data.get("season", 2026)),
            "scoring": {"type": self._infer_type(scoring), "rules": scoring},
            "roster": {
                "starters": starters,
                "bench": bench,
                "ir_slots": roster_positions.count("IR"),
            },
        }

    def fetch_roster(self, league_id: str) -> NormalizedRoster:
        rosters = self._get(f"/league/{league_id}/rosters")
        users = {u["user_id"]: u for u in self._get(f"/league/{league_id}/users")}
        teams = []
        for r in rosters:
            owner = users.get(r.get("owner_id"), {})
            teams.append(
                {
                    "team_id": r.get("roster_id"),
                    "owner": owner.get("display_name"),
                    "players": r.get("players", []) or [],
                    "starters": r.get("starters", []) or [],
                }
            )
        return NormalizedRoster(league_id=league_id, teams=teams)

    def fetch_transactions(self, league_id: str, week: int = 1) -> list[dict[str, Any]]:
        return self._get(f"/league/{league_id}/transactions/{week}") or []

    def fetch_adp(self) -> list[dict[str, Any]]:
        # Sleeper exposes trending adds as a usage proxy; true ADP comes from a
        # projections partner. Return trending adds as pickup velocity.
        trending = self._get("/players/nfl/trending/add?limit=50") or []
        return [
            {"player_id": t.get("player_id"), "pickup_velocity": t.get("count", 0)}
            for t in trending
        ]

    def fetch_player_stats(self, player_id: str) -> dict[str, Any]:
        players = self._get("/players/nfl")  # large; cache daily in production
        return players.get(player_id, {})

    @staticmethod
    def _infer_type(scoring: dict[str, Any]) -> str:
        rec = scoring.get("rec", 0)
        if rec >= 1:
            return "PPR"
        if rec >= 0.5:
            return "Half-PPR"
        return "Standard"
