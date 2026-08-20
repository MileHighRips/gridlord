"""Public-content scrapers (respecting each site's public surface).

Pulls YouTube channel RSS (fully public) from major fantasy analysts — including
Flock Fantasy, whose free videos surface risers/fallers and draft strategy — and
turns titles/descriptions into player *buzz* signal (mention velocity + riser vs
faller sentiment). This is how we capture what the premium analysts are talking
about without their paywalled feeds.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import httpx

_UA = {"User-Agent": "Mozilla/5.0 (GridLord/1.0)"}

# Fantasy analyst YouTube handles -> display source name.
YOUTUBE_CHANNELS = {
    "@FlockFantasy": "Flock Fantasy",
    "@FantasyPros": "FantasyPros",
    "@TheFantasyFootballers": "Fantasy Footballers",
    "@EstablishTheRun": "Establish the Run",
    "@FootballGuys": "Footballguys",
    "@FantasyLife": "Fantasy Life",
}

RISER_WORDS = ("skyrocket", "rising", "riser", "buy", "breakout", "league winner",
               "smash", "target", "up ", "🚀", "📈", "sleeper", "must draft",
               "value", "ascend", "hype")
FALLER_WORDS = ("avoid", "fade", "bust", "falling", "faller", "sell", "concern",
                "overrated", "down ", "📉", "trap", "red flag", "worry", "injury")

_channel_cache: dict[str, str | None] = {}


def resolve_youtube_channel(handle: str) -> str | None:
    """Resolve a @handle to a UC… channel id via the public channel page."""
    if handle in _channel_cache:
        return _channel_cache[handle]
    cid = None
    try:
        with httpx.Client(timeout=12, headers=_UA, follow_redirects=True) as c:
            html = c.get(f"https://www.youtube.com/{handle}/videos").text
        m = re.search(r'"channelId":"(UC[\w-]{22})"', html) or re.search(
            r"channel/(UC[\w-]{22})", html
        )
        cid = m.group(1) if m else None
    except Exception:
        cid = None
    _channel_cache[handle] = cid
    return cid


@dataclass
class InsightItem:
    source: str
    title: str
    summary: str
    url: str | None
    published: str | None
    sentiment: str  # "riser" | "faller" | "neutral"


def _sentiment(text: str) -> str:
    low = text.lower()
    r = sum(1 for w in RISER_WORDS if w in low)
    f = sum(1 for w in FALLER_WORDS if w in low)
    if r > f:
        return "riser"
    if f > r:
        return "faller"
    return "neutral"


def fetch_youtube_insights(max_per_channel: int = 12) -> list[InsightItem]:
    """Pull recent videos from each analyst channel as insight items."""
    items: list[InsightItem] = []
    with httpx.Client(timeout=15, headers=_UA, follow_redirects=True) as c:
        for handle, source in YOUTUBE_CHANNELS.items():
            cid = resolve_youtube_channel(handle)
            if not cid:
                continue
            try:
                xml = c.get(
                    f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
                ).text
            except Exception:
                continue
            entries = re.findall(r"<entry>(.*?)</entry>", xml, re.S)[:max_per_channel]
            for e in entries:
                title = _tag(e, "title")
                link_m = re.search(r'<link rel="alternate" href="([^"]+)"', e)
                published = _tag(e, "published")
                desc = _tag(e, "media:description") or ""
                if not title:
                    continue
                items.append(
                    InsightItem(
                        source=f"{source} (YouTube)",
                        title=title,
                        summary=desc[:600],
                        url=link_m.group(1) if link_m else None,
                        published=published,
                        sentiment=_sentiment(f"{title} {desc}"),
                    )
                )
    return items


def _tag(xml: str, tag: str) -> str:
    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", xml, re.S)
    return _unescape(m.group(1).strip()) if m else ""


def _unescape(s: str) -> str:
    return (
        s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        .replace("&#39;", "'").replace("&quot;", '"')
    )


@dataclass
class PlayerBuzz:
    mentions: int = 0
    riser_hits: int = 0
    faller_hits: int = 0
    sources: set[str] = field(default_factory=set)


def compute_player_buzz(
    insights: list[InsightItem], player_names: list[str]
) -> dict[str, PlayerBuzz]:
    """Count analyst mentions of each player (buzz velocity) with sentiment.

    Requires both the first and last name tokens to appear so common surnames
    (e.g. multiple "Brown"s) don't collide into false positives.
    """
    import re as _re

    def norm(s: str) -> str:
        return _re.sub(r"[^a-z ]", " ", s.lower())

    buzz: dict[str, PlayerBuzz] = {}
    parsed = []
    for name in player_names:
        toks = norm(name).split()
        if len(toks) >= 2:
            parsed.append((name, toks[0], toks[-1]))
    for it in insights:
        blob = " " + norm(f"{it.title} {it.summary}") + " "
        for name, first, last in parsed:
            if len(last) < 4:
                continue
            # Require the full surname and the first name (or its initial) present.
            if f" {last} " in blob and (
                f" {first} " in blob or f" {first[0]} " in blob
            ):
                b = buzz.setdefault(name, PlayerBuzz())
                b.mentions += 1
                b.sources.add(it.source)
                if it.sentiment == "riser":
                    b.riser_hits += 1
                elif it.sentiment == "faller":
                    b.faller_hits += 1
    return buzz
