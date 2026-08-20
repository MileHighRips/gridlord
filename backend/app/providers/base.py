"""Unified Fantasy Provider Interface abstract base."""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NormalizedRoster:
    league_id: str
    teams: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class RateLimitPolicy:
    max_requests_per_minute: int = 60
    max_retries: int = 4
    backoff_base_seconds: float = 0.5


class FantasyProvider(abc.ABC):
    """Adapter interface every provider must implement.

    Concrete adapters translate provider-specific payloads into GridironIQ's
    normalized dicts (see :mod:`app.mapping`).
    """

    name: str = "base"
    rate_limit = RateLimitPolicy()

    @abc.abstractmethod
    def fetch_league(self, league_id: str) -> dict[str, Any]:
        """Return league metadata + settings in canonical shape."""

    @abc.abstractmethod
    def fetch_roster(self, league_id: str) -> NormalizedRoster:
        """Return all team rosters for the league."""

    @abc.abstractmethod
    def fetch_transactions(self, league_id: str) -> list[dict[str, Any]]:
        """Return adds/drops/trades/waivers."""

    @abc.abstractmethod
    def fetch_adp(self) -> list[dict[str, Any]]:
        """Return ADP entries (player, adp, format)."""

    @abc.abstractmethod
    def fetch_player_stats(self, player_id: str) -> dict[str, Any]:
        """Return raw stat line(s) for a player."""

    # ---- Write operations (best-effort; may be unsupported per provider) ---- #
    def submit_lineup(self, league_id: str, week: int, lineup: dict[str, Any]) -> bool:
        raise NotImplementedError(f"{self.name} does not support submit_lineup")

    def submit_trade(self, league_id: str, trade: dict[str, Any]) -> bool:
        raise NotImplementedError(f"{self.name} does not support submit_trade")

    @property
    def supports_write(self) -> bool:
        return False
