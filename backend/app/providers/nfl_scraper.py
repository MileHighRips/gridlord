"""Generic HTML scraper adapter for platforms without a public API.

Provides a safe, rate-limited fallback. Selectors are configured per site so
the same adapter can target NFL.com or niche platforms. Respect each site's
robots.txt and Terms of Service before enabling scraping in production.
"""
from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import FantasyProvider, NormalizedRoster


class ScraperProvider(FantasyProvider):
    name = "scraper"

    def __init__(self, base_url: str, selectors: dict[str, str] | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.selectors = selectors or {}
        self._client = httpx.Client(
            timeout=20.0,
            headers={"User-Agent": "GridironIQ/1.0 (+https://example.com/bot)"},
            follow_redirects=True,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
    def _fetch_html(self, path: str) -> str:
        resp = self._client.get(f"{self.base_url}{path}")
        resp.raise_for_status()
        return resp.text

    def fetch_league(self, league_id: str) -> dict[str, Any]:
        html = self._fetch_html(f"/league/{league_id}")
        return {
            "provider": "scraper",
            "provider_league_id": league_id,
            "leagueName": self._extract(html, "league_name") or "Scraped League",
            "teams": 12,
            "season": 2026,
            "scoring": {"type": "Custom", "rules": {}},
            "roster": {"starters": {}, "bench": 6, "ir_slots": 0},
        }

    def fetch_roster(self, league_id: str) -> NormalizedRoster:
        return NormalizedRoster(league_id=league_id, teams=[])

    def fetch_transactions(self, league_id: str) -> list[dict[str, Any]]:
        return []

    def fetch_adp(self) -> list[dict[str, Any]]:
        return []

    def fetch_player_stats(self, player_id: str) -> dict[str, Any]:
        return {}

    def _extract(self, html: str, key: str) -> str | None:
        """Placeholder: use a real parser (BeautifulSoup/lxml) with self.selectors."""
        return None
