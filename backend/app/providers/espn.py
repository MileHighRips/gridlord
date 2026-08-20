"""ESPN adapter.

ESPN's fantasy API is private/undocumented. Public leagues read via the
`lm-api-reads.fantasy.espn.com` endpoint; private leagues require the `SWID` and
`espn_s2` cookies. Write operations are not officially supported.
"""
from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import settings
from .base import FantasyProvider, NormalizedRoster

_BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons"

# ESPN scoring stat id -> canonical stat key (subset of the full map).
ESPN_SCORING_MAP = {
    "3": "pass_yd", "4": "pass_td", "20": "interception",
    "24": "rush_yd", "25": "rush_td",
    "42": "rec_yd", "43": "rec_td", "53": "reception",
    "72": "fumble_lost", "17": "pat_made",
}


class ESPNProvider(FantasyProvider):
    name = "espn"

    def __init__(self, season: int = 2026) -> None:
        self.season = season
        cookies = {}
        if settings.espn_swid and settings.espn_s2:
            cookies = {"SWID": settings.espn_swid, "espn_s2": settings.espn_s2}
        self._client = httpx.Client(timeout=20.0, cookies=cookies)

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=0.5, max=8))
    def _get(self, league_id: str, views: list[str]) -> Any:
        url = f"{_BASE}/{self.season}/segments/0/leagues/{league_id}"
        params = [("view", v) for v in views]
        resp = self._client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    def fetch_league(self, league_id: str) -> dict[str, Any]:
        data = self._get(league_id, ["mSettings"])
        block = data.get("settings", {})
        roster = block.get("rosterSettings", {}).get("lineupSlotCounts", {})
        scoring_items = block.get("scoringSettings", {}).get("scoringItems", [])
        rules = {}
        for item in scoring_items:
            key = ESPN_SCORING_MAP.get(str(item.get("statId")))
            if key:
                rules[key] = item.get("points", 0)
        return {
            "provider": "espn",
            "provider_league_id": league_id,
            "leagueName": block.get("name", "ESPN League"),
            "teams": block.get("size", 12),
            "season": self.season,
            "scoring": {"type": "Custom", "rules": rules},
            "roster": {
                "starters": self._slots(roster),
                "bench": roster.get("20", 6),
                "ir_slots": roster.get("21", 0),
            },
        }

    def fetch_roster(self, league_id: str) -> NormalizedRoster:
        data = self._get(league_id, ["mRoster", "mTeam"])
        teams = []
        for t in data.get("teams", []):
            entries = t.get("roster", {}).get("entries", [])
            teams.append(
                {
                    "team_id": t.get("id"),
                    "owner": t.get("name") or f"Team {t.get('id')}",
                    "players": [e.get("playerId") for e in entries],
                }
            )
        return NormalizedRoster(league_id=league_id, teams=teams)

    def fetch_transactions(self, league_id: str) -> list[dict[str, Any]]:
        data = self._get(league_id, ["mTransactions2"])
        return data.get("transactions", []) or []

    def fetch_adp(self) -> list[dict[str, Any]]:
        return []  # ESPN exposes ADP via players_wl view; omitted for brevity

    def fetch_player_stats(self, player_id: str) -> dict[str, Any]:
        return {}

    @staticmethod
    def _slots(counts: dict[str, Any]) -> dict[str, int]:
        mapping = {"0": "QB", "2": "RB", "4": "WR", "6": "TE",
                   "23": "FLEX", "16": "DEF", "17": "K"}
        out: dict[str, int] = {}
        for slot_id, cnt in counts.items():
            pos = mapping.get(str(slot_id))
            if pos and cnt:
                out[pos] = cnt
        return out
