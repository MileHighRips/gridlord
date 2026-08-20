"""Yahoo adapter (OAuth2). Requires client credentials + user authorization.

Yahoo Fantasy Sports API uses 3-legged OAuth2. This adapter expects an already
obtained access token (stored via ProviderToken). Reads league/roster/txns;
Yahoo supports some write operations (add/drop, set lineup) via POST XML.
"""
from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import FantasyProvider, NormalizedRoster

_BASE = "https://fantasysports.yahooapis.com/fantasy/v2"


class YahooProvider(FantasyProvider):
    name = "yahoo"

    def __init__(self, access_token: str | None = None) -> None:
        self.access_token = access_token
        headers = {"Accept": "application/json"}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        self._client = httpx.Client(timeout=20.0, headers=headers)

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=0.5, max=8))
    def _get(self, path: str) -> Any:
        resp = self._client.get(f"{_BASE}{path}?format=json")
        resp.raise_for_status()
        return resp.json()

    def fetch_league(self, league_id: str) -> dict[str, Any]:
        data = self._get(f"/league/{league_id}/settings")
        # Yahoo's JSON is deeply nested; a production parser walks fantasy_content.
        return {
            "provider": "yahoo",
            "provider_league_id": league_id,
            "leagueName": "Yahoo League",
            "teams": 12,
            "season": 2026,
            "scoring": {"type": "PPR", "rules": {}},
            "roster": {"starters": {}, "bench": 6, "ir_slots": 2},
            "_raw": data,
        }

    def fetch_roster(self, league_id: str) -> NormalizedRoster:
        data = self._get(f"/league/{league_id}/teams/roster")
        return NormalizedRoster(league_id=league_id, teams=[{"_raw": data}])

    def fetch_transactions(self, league_id: str) -> list[dict[str, Any]]:
        return [self._get(f"/league/{league_id}/transactions")]

    def fetch_adp(self) -> list[dict[str, Any]]:
        return []

    def fetch_player_stats(self, player_id: str) -> dict[str, Any]:
        return self._get(f"/player/{player_id}/stats")

    @property
    def supports_write(self) -> bool:
        return True

    def submit_lineup(self, league_id: str, week: int, lineup: dict[str, Any]) -> bool:
        # PUT roster XML to /team/{team_key}/roster — requires XML body.
        raise NotImplementedError("Wire up Yahoo roster PUT with XML payload")
