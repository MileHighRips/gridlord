"""Provider registry."""
from __future__ import annotations

from .base import FantasyProvider
from .espn import ESPNProvider
from .nfl_scraper import ScraperProvider
from .sleeper import SleeperProvider
from .yahoo import YahooProvider


def get_provider(name: str, **kwargs) -> FantasyProvider:
    """Factory for provider adapters by name."""
    name = name.lower()
    if name == "sleeper":
        return SleeperProvider(**kwargs)
    if name == "espn":
        return ESPNProvider(**kwargs)
    if name == "yahoo":
        return YahooProvider(**kwargs)
    if name in ("nfl", "scraper"):
        return ScraperProvider(kwargs.get("base_url", "https://fantasy.nfl.com"))
    raise ValueError(f"Unknown provider: {name}")


PROVIDERS = ["sleeper", "espn", "yahoo", "nfl"]

__all__ = ["FantasyProvider", "get_provider", "PROVIDERS"]
