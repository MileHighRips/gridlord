"""Pluggable multi-source framework for rankings and news.

Live adapters pull real data now (Sleeper projections, FantasyPros expert
consensus, and six news RSS feeds). Premium/credentialed adapters are registered
with ``available = False`` and a reason, so the Sources page shows exactly what's
live and what lights up once you add an API key or subscription cookie.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

_UA = {"User-Agent": "Mozilla/5.0 (GridLord/1.0)"}


# --------------------------------------------------------------------------- #
# Ranking sources
# --------------------------------------------------------------------------- #
@dataclass
class RankingRowRaw:
    name: str
    position: str
    team: str | None
    rank: float
    tier: int | None = None
    rank_std: float | None = None  # expert disagreement
    delta: float | None = None  # recent movement (+ = rising)
    adp: float | None = None
    bye_week: int | None = None
    ids: dict[str, str] = field(default_factory=dict)


@dataclass
class SourceStatus:
    key: str
    name: str
    kind: str  # "rankings" | "news"
    available: bool
    weight: float
    note: str


class RankingSource:
    key = "base"
    name = "Base"
    weight = 1.0
    available = True
    note = ""

    def fetch(self) -> list[RankingRowRaw]:  # pragma: no cover - interface
        raise NotImplementedError

    def status(self) -> SourceStatus:
        return SourceStatus(self.key, self.name, "rankings", self.available,
                            self.weight, self.note)


class FantasyProsSource(RankingSource):
    key = "fantasypros"
    name = "FantasyPros ECR"
    weight = 1.0
    available = True
    note = "Live expert consensus (aggregates 100+ analysts)."

    URL = (
        "https://partners.fantasypros.com/api/v1/consensus-rankings.php"
        "?sport=NFL&year={year}&week=0&experts=available&position=ALL"
        "&type=ST&scoring={scoring}&format=json"
    )

    def __init__(self, year: int = 2026, scoring: str = "PPR") -> None:
        self.year = year
        self.scoring = scoring

    def fetch(self) -> list[RankingRowRaw]:
        url = self.URL.format(year=self.year, scoring=self.scoring)
        with httpx.Client(timeout=25, headers=_UA) as c:
            data = c.get(url).json()
        rows: list[RankingRowRaw] = []
        for p in data.get("players", []):
            rows.append(
                RankingRowRaw(
                    name=p.get("player_name", ""),
                    position=p.get("player_position_id", ""),
                    team=p.get("player_team_id"),
                    rank=float(p.get("rank_ecr") or 999),
                    tier=p.get("tier"),
                    rank_std=float(p.get("rank_std") or 0) or None,
                    delta=float(p.get("player_ecr_delta") or 0) or None,
                    adp=None,
                    bye_week=p.get("player_bye_week"),
                    ids={
                        "yahoo": str(p.get("player_yahoo_id") or ""),
                        "cbs": str(p.get("cbs_player_id") or ""),
                    },
                )
            )
        return rows


class _PremiumRankingStub(RankingSource):
    """A registered-but-inactive premium ranking provider."""

    available = False

    def __init__(self, key: str, name: str, note: str, weight: float = 1.0) -> None:
        self.key = key
        self.name = name
        self.note = note
        self.weight = weight

    def fetch(self) -> list[RankingRowRaw]:
        return []


PREMIUM_RANKING_SOURCES = [
    _PremiumRankingStub("flock", "Flock Fantasy",
                        "Add API/subscription — league-size-aware ADP & tiers.", 1.1),
    _PremiumRankingStub("pff", "PFF Fantasy",
                        "Requires PFF subscription token.", 1.1),
    _PremiumRankingStub("etr", "Establish the Run",
                        "Requires ETR subscription.", 1.1),
    _PremiumRankingStub("draftsharks", "Draft Sharks",
                        "Requires Draft Sharks API key.", 1.0),
    _PremiumRankingStub("footballguys", "Footballguys",
                        "Requires Footballguys subscription.", 1.0),
    _PremiumRankingStub("fantasylife", "Fantasy Life",
                        "Requires Fantasy Life access.", 1.0),
    _PremiumRankingStub("rotoviz", "Rotoviz",
                        "Requires Rotoviz subscription.", 1.0),
]


def ranking_sources() -> list[RankingSource]:
    return [FantasyProsSource()] + PREMIUM_RANKING_SOURCES


# --------------------------------------------------------------------------- #
# News sources
# --------------------------------------------------------------------------- #
@dataclass
class NewsSourceDef:
    key: str
    name: str
    url: str | None
    available: bool
    note: str = ""


LIVE_NEWS_FEEDS = [
    NewsSourceDef("pft", "ProFootballTalk", "https://profootballtalk.nbcsports.com/feed/", True),
    NewsSourceDef("pff", "PFF", "https://www.pff.com/feed", True),
    NewsSourceDef("espn", "ESPN NFL", "https://www.espn.com/espn/rss/nfl/news", True),
    NewsSourceDef("rotowire", "RotoWire", "https://www.rotowire.com/rss/news.php?sport=NFL", True),
    NewsSourceDef("cbs", "CBS Sports", "https://www.cbssports.com/rss/headlines/nfl/", True),
    NewsSourceDef("yardbarker", "Yardbarker NFL", "https://www.yardbarker.com/rss/sport/2", True),
    NewsSourceDef("beat", "Beat writers & local (32 teams)", None, True,
                  "Google News per-team: beat writers, local papers, pressers."),
    NewsSourceDef("youtube", "Analyst buzz (Flock/FantasyPros/Footballers/ETR/FBG/FL)",
                  None, True, "Public YouTube feeds — riser/faller sentiment."),
]

PREMIUM_NEWS_SOURCES = [
    NewsSourceDef("fantasypros_news", "FantasyPros News", None, False,
                  "Enable with FantasyPros API key."),
    NewsSourceDef("theathletic", "The Athletic", None, False,
                  "Requires The Athletic subscription."),
    NewsSourceDef("nflnetwork", "NFL Network", None, False,
                  "Requires NFL Network feed access."),
    NewsSourceDef("fantasylife_news", "Fantasy Life", None, False,
                  "Requires Fantasy Life access."),
    NewsSourceDef("schefter", "Adam Schefter (X)", None, False,
                  "Requires X/Twitter API bearer token."),
    NewsSourceDef("rapoport", "Ian Rapoport (X)", None, False,
                  "Requires X/Twitter API bearer token."),
    NewsSourceDef("schultz", "Jordan Schultz (X)", None, False,
                  "Requires X/Twitter API bearer token."),
]


def all_source_status() -> list[dict[str, Any]]:
    """Combined live + pending status for the Sources page."""
    out: list[dict[str, Any]] = []
    for s in ranking_sources():
        st = s.status()
        out.append({"key": st.key, "name": st.name, "kind": "rankings",
                    "available": st.available, "weight": st.weight, "note": st.note})
    for f in LIVE_NEWS_FEEDS:
        out.append({"key": f.key, "name": f.name, "kind": "news",
                    "available": True, "weight": 1.0, "note": "Live RSS feed."})
    for f in PREMIUM_NEWS_SOURCES:
        out.append({"key": f.key, "name": f.name, "kind": "news",
                    "available": False, "weight": 1.0, "note": f.note})
    return out
