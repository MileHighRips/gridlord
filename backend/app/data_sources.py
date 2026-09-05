"""Live data sources: Sleeper projections/stats/ADP + RSS news.

All projections are re-scored into the league's *exact* scoring (including
yardage bonuses, estimated from per-game production) so rankings reflect the
user's real league rather than a generic PPR number.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from .engine.scoring import DEFAULT_SCORING, points_allowed_score

SLEEPER = "https://api.sleeper.com"
SLEEPER_APP = "https://api.sleeper.app/v1"
_UA = {"User-Agent": "Mozilla/5.0 (GridLord/1.0)"}

# Sleeper raw stat key -> our scoring-engine key (counting stats only).
SLEEPER_STAT_MAP = {
    "pass_yd": "pass_yd",
    "pass_td": "pass_td",
    "pass_int": "interception",
    "rush_yd": "rush_yd",
    "rush_td": "rush_td",
    "rec": "receptions",  # alias for the `reception` weight
    "rec_yd": "rec_yd",
    "rec_td": "rec_td",
    "fum_lost": "fumble_lost",
}

# Yardage bonus tiers (threshold_yards, points) per league rules.
PASS_BONUS = [(200, 3.0), (250, 5.0), (300, 7.0)]
RUSH_BONUS = [(75, 3.0), (100, 5.0), (150, 7.0)]
REC_BONUS = [(75, 3.0), (100, 5.0), (150, 7.0)]

# Per-game yardage coefficient of variation, used to estimate bonus frequency.
CV_PASS, CV_RUSH, CV_REC = 0.32, 0.55, 0.55

# Projection volatility (std / mean) by position.
POS_CV = {"QB": 0.20, "RB": 0.30, "WR": 0.30, "TE": 0.33, "K": 0.24, "DEF": 0.30}

# injury_status -> season availability factor and a human label.
INJURY_FACTOR = {
    "IR": (0.45, "On IR"),
    "PUP": (0.5, "On PUP"),
    "Out": (0.6, "Ruled out"),
    "Suspended": (0.6, "Suspended"),
    "Doubtful": (0.8, "Doubtful"),
    "Questionable": (0.97, "Questionable"),
    "Sus": (0.6, "Suspended"),
}


@dataclass
class PlayerProjectionRow:
    sleeper_id: str
    name: str
    position: str
    team: str | None
    injury_status: str | None
    injury_note: str | None
    years_exp: int | None
    mean_points: float
    std_points: float
    adp: float | None
    last_year_points: float | None = None
    raw_stats: dict[str, float] = field(default_factory=dict)
    drivers: list[str] = field(default_factory=list)


# Sleeper stat keys we persist so projections can be re-scored when league
# scoring changes (offense + kicker + defense inputs).
SCORING_STAT_KEYS = (
    "pass_yd", "pass_td", "pass_int", "rush_yd", "rush_td", "rec", "rec_yd",
    "rec_td", "fum_lost", "pass_2pt", "rush_2pt", "rec_2pt", "gp",
    "fgm_40_49", "fgm_50p", "fgmiss_40_49", "fgmiss_50p", "xpm", "xpmiss", "pts_std",
    "sack", "int", "fum_rec", "def_fum_td", "def_kr_td", "blk_kick",
    "pts_allow_0", "pts_allow_1_6", "pts_allow_7_13", "pts_allow_14_20",
    "pts_allow_21_27", "pts_allow_28_34", "pts_allow_35p",
)


def trim_stats(stats: dict[str, Any]) -> dict[str, float]:
    """Keep only scoring-relevant stat keys for compact storage."""
    return {k: float(stats[k]) for k in SCORING_STAT_KEYS if stats.get(k) is not None}



def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def estimate_yardage_bonus(total_yd: float, gp: float, tiers, cv: float) -> float:
    """Expected season bonus points from per-game yardage crossing tier thresholds.

    Tiers are non-cumulative (only the highest reached threshold pays each game),
    so E[bonus/game] = Σ (b_i - b_{i-1}) · P(X ≥ t_i), scaled by games played.
    """
    if gp <= 0 or total_yd <= 0:
        return 0.0
    per_game = total_yd / gp
    sd = max(cv * per_game, 1.0)
    prev = 0.0
    exp_per_game = 0.0
    for threshold, pts in tiers:
        p = 1.0 - _norm_cdf((threshold - per_game) / sd)
        exp_per_game += (pts - prev) * p
        prev = pts
    return round(exp_per_game * gp, 2)


def _bonus_tiers(scoring: dict[str, float], prefix: str) -> list[tuple[int, float]]:
    """Extract bonus (threshold, points) tiers for a prefix from a scoring dict."""
    tiers = []
    for k, v in scoring.items():
        if k.startswith(prefix):
            try:
                tiers.append((int(k[len(prefix):]), float(v)))
            except ValueError:
                continue
    return sorted(tiers)


def score_offense(stats: dict[str, Any], scoring: dict[str, float] | None = None) -> float:
    """League points for an offensive season stat line (base + estimated bonuses).

    Honors a custom `scoring` dict so re-scoring reflects saved league settings
    (per-stat weights AND yardage bonus thresholds).
    """
    sc = scoring or DEFAULT_SCORING

    def w(key: str) -> float:
        return float(sc.get(key, DEFAULT_SCORING.get(key, 0.0)))

    base = 0.0
    base += float(stats.get("pass_yd", 0) or 0) * w("pass_yd")
    base += float(stats.get("pass_td", 0) or 0) * w("pass_td")
    base += float(stats.get("pass_int", 0) or 0) * w("interception")
    base += float(stats.get("rush_yd", 0) or 0) * w("rush_yd")
    base += float(stats.get("rush_td", 0) or 0) * w("rush_td")
    base += float(stats.get("rec", 0) or 0) * w("reception")
    base += float(stats.get("rec_yd", 0) or 0) * w("rec_yd")
    base += float(stats.get("rec_td", 0) or 0) * w("rec_td")
    base += float(stats.get("fum_lost", 0) or 0) * w("fumble_lost")
    two_pt = sum(float(stats.get(k, 0) or 0) for k in ("pass_2pt", "rush_2pt", "rec_2pt"))
    base += two_pt * w("two_pt")

    gp = float(stats.get("gp", 0) or 0) or 17.0
    pass_tiers = _bonus_tiers(sc, "bonus_pass_yd_") or PASS_BONUS
    rush_tiers = _bonus_tiers(sc, "bonus_rush_yd_") or RUSH_BONUS
    rec_tiers = _bonus_tiers(sc, "bonus_rec_yd_") or REC_BONUS
    # If the league explicitly has no bonus keys, don't invent them.
    has_bonus = any(k.startswith("bonus_") for k in sc)
    if scoring is not None and not has_bonus:
        pass_tiers = rush_tiers = rec_tiers = []
    bonus = (
        estimate_yardage_bonus(float(stats.get("pass_yd", 0) or 0), gp, pass_tiers, CV_PASS)
        + estimate_yardage_bonus(float(stats.get("rush_yd", 0) or 0), gp, rush_tiers, CV_RUSH)
        + estimate_yardage_bonus(float(stats.get("rec_yd", 0) or 0), gp, rec_tiers, CV_REC)
    )
    return round(base + bonus, 1)


def score_kicker(stats: dict[str, Any]) -> float:
    """Approximate league K points from Sleeper distance buckets."""
    fgm_40_49 = float(stats.get("fgm_40_49", 0) or 0)
    fgm_50p = float(stats.get("fgm_50p", 0) or 0)
    fgmiss_40_49 = float(stats.get("fgmiss_40_49", 0) or 0)
    fgmiss_50p = float(stats.get("fgmiss_50p", 0) or 0)
    xpm = float(stats.get("xpm", 0) or 0)
    xpmiss = float(stats.get("xpmiss", 0) or 0)
    # Short FGs aren't bucketed by Sleeper; approximate from pts_std residual.
    pts_std = float(stats.get("pts_std", 0) or 0)
    long_pts = fgm_40_49 * 3 + fgm_50p * 5 + xpm  # sleeper-ish baseline
    short_makes = max(0.0, (pts_std - long_pts) / 3.0)
    return round(
        short_makes * 3 + fgm_40_49 * 4 + fgm_50p * 5 + xpm * 1
        - fgmiss_40_49 * 3 - fgmiss_50p * 3 - xpmiss * 1,
        1,
    )


def score_defense(stats: dict[str, Any]) -> float:
    """Approximate league DST points from Sleeper counting stats + PA buckets."""
    pts = (
        float(stats.get("sack", 0) or 0) * 1
        + float(stats.get("int", 0) or 0) * 2
        + float(stats.get("fum_rec", 0) or 0) * 2
        + float(stats.get("def_fum_td", 0) or 0) * 6
        + float(stats.get("def_kr_td", 0) or 0) * 6
        + float(stats.get("blk_kick", 0) or 0) * 2
    )
    # Points-allowed buckets are counts of games in each tier.
    pa_buckets = {
        "pts_allow_0": 0, "pts_allow_1_6": 6, "pts_allow_7_13": 13,
        "pts_allow_14_20": 20, "pts_allow_21_27": 27, "pts_allow_28_34": 34,
        "pts_allow_35p": 35,
    }
    for key, pa in pa_buckets.items():
        games = float(stats.get(key, 0) or 0)
        if games:
            pts += points_allowed_score(pa) * games
    return round(pts, 1)


def _availability(injury_status: str | None) -> tuple[float, str | None]:
    if not injury_status:
        return 1.0, None
    return INJURY_FACTOR.get(injury_status, (1.0, injury_status))


def fetch_projection_rows(season: int = 2026) -> list[PlayerProjectionRow]:
    """Fetch and score 2026 season projections for all fantasy positions."""
    positions = ["QB", "RB", "WR", "TE", "K", "DEF"]
    q = "&".join(f"position[]={p}" for p in positions)
    url = f"{SLEEPER}/projections/nfl/{season}?season_type=regular&order_by=pts_ppr&{q}"
    with httpx.Client(timeout=40) as c:
        data = c.get(url).json()

    rows: list[PlayerProjectionRow] = []
    for item in data:
        p = item.get("player") or {}
        pos = p.get("position")
        if pos not in positions:
            continue
        stats = item.get("stats") or {}
        pid = str(item.get("player_id"))

        if pos == "K":
            mean = score_kicker(stats)
        elif pos == "DEF":
            mean = score_defense(stats)
            name = f"{p.get('team_abbr') or item.get('team') or pid} DST"
        else:
            mean = score_offense(stats)

        if pos == "DEF":
            name = f"{item.get('team') or pid} DST"
        else:
            first = p.get("first_name") or ""
            last = p.get("last_name") or ""
            name = f"{first} {last}".strip() or str(pid)

        if mean <= 0:
            continue

        cv = POS_CV.get(pos, 0.3)
        std = round(mean * cv, 1)
        adp = stats.get("adp_ppr")
        adp = None if adp is None or adp >= 990 else float(adp)
        inj = p.get("injury_status")
        note = p.get("injury_notes") or p.get("injury_body_part")

        rows.append(
            PlayerProjectionRow(
                sleeper_id=pid,
                name=name,
                position=pos,
                team=item.get("team") or p.get("team"),
                injury_status=inj,
                injury_note=note,
                years_exp=p.get("years_exp"),
                mean_points=mean,
                std_points=std,
                adp=adp,
                raw_stats=trim_stats(stats),
            )
        )
    return rows


def fetch_last_year_points(season: int = 2025) -> dict[str, float]:
    """Map sleeper_id -> prior-season league points for context/blending."""
    positions = ["QB", "RB", "WR", "TE", "K", "DEF"]
    q = "&".join(f"position[]={p}" for p in positions)
    url = f"{SLEEPER}/stats/nfl/{season}?season_type=regular&order_by=pts_ppr&{q}"
    with httpx.Client(timeout=40) as c:
        data = c.get(url).json()
    out: dict[str, float] = {}
    for item in data:
        p = item.get("player") or {}
        pos = p.get("position")
        stats = item.get("stats") or {}
        pid = str(item.get("player_id"))
        if pos == "K":
            out[pid] = score_kicker(stats)
        elif pos == "DEF":
            out[pid] = score_defense(stats)
        elif pos in positions:
            out[pid] = score_offense(stats)
    return out


def fetch_trending_adds(limit: int = 100) -> dict[str, int]:
    """sleeper_id -> add count (waiver pickup velocity)."""
    url = f"{SLEEPER_APP}/players/nfl/trending/add?limit={limit}"
    with httpx.Client(timeout=20) as c:
        data = c.get(url).json()
    return {str(t.get("player_id")): int(t.get("count", 0)) for t in data}


# --------------------------------------------------------------------------- #
# News (RSS) + news intelligence
# --------------------------------------------------------------------------- #
# Six live feeds (premium-adjacent where a public RSS exists, e.g. PFF/PFT).
NEWS_FEEDS = [
    ("ProFootballTalk", "https://profootballtalk.nbcsports.com/feed/"),
    ("PFF", "https://www.pff.com/feed"),
    ("ESPN NFL", "https://www.espn.com/espn/rss/nfl/news"),
    ("RotoWire", "https://www.rotowire.com/rss/news.php?sport=NFL"),
    ("CBS Sports", "https://www.cbssports.com/rss/headlines/nfl/"),
    ("Yardbarker NFL", "https://www.yardbarker.com/rss/sport/2"),
]

INJURY_WORDS = ("injur", "hurt", "out ", "questionable", "doubtful", "ir ", "acl",
                "hamstring", "ankle", "concussion", "surgery", "sprain", "strain",
                "carted", "mri")
ROLE_WORDS = ("start", "promot", "depth chart", "snap", "target", "workload",
              "bench", "rotation", "committee", "lead back", "wr1", "rb1")
PRACTICE_WORDS = {
    "dnp": "DNP", "did not practice": "DNP", "limited": "Limited",
    "full practice": "Full", "full participant": "Full",
}
# Coach-speak patterns historically low-signal / misleading.
COACHSPEAK_PATTERNS = (
    "want to get him more involved", "day-to-day", "we'll see", "game-time decision",
    "feel good about", "committee approach", "ramp him up", "pitch count",
    "expanded role", "when he's ready", "trust the process",
)


@dataclass
class NewsRow:
    source: str
    headline: str
    summary: str | None
    url: str | None
    tags: str
    published: Any | None


def extractive_summary(text: str, max_len: int = 220) -> str | None:
    """Cheap NLP: first informative sentence(s), trimmed to an actionable blurb."""
    if not text:
        return None
    # Strip HTML tags.
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    out = ""
    for s in sentences:
        if len(out) + len(s) > max_len:
            break
        out += (" " if out else "") + s
    return out[:max_len] or None


def practice_status(text: str) -> str | None:
    low = text.lower()
    for kw, label in PRACTICE_WORDS.items():
        if kw in low:
            return label
    return None


def coach_speak_flag(text: str) -> bool:
    low = text.lower()
    return any(p in low for p in COACHSPEAK_PATTERNS)


def tag_news(title: str, summary: str) -> list[str]:
    blob = f"{title} {summary}".lower()
    tags: list[str] = []
    if any(w in blob for w in INJURY_WORDS):
        tags.append("injury")
    if any(w in blob for w in ROLE_WORDS):
        tags.append("role_change")
    if practice_status(blob):
        tags.append("practice")
    if coach_speak_flag(blob):
        tags.append("coach_speak")
    return tags or ["news"]


def fetch_news(max_items: int = 40) -> list[NewsRow]:
    import feedparser

    rows: list[NewsRow] = []
    for source, feed_url in NEWS_FEEDS:
        try:
            parsed = feedparser.parse(feed_url)
        except Exception:
            continue
        for e in parsed.entries[:max_items]:
            title = getattr(e, "title", "") or ""
            summary_raw = getattr(e, "summary", "") or ""
            rows.append(
                NewsRow(
                    source=source,
                    headline=title[:390],
                    summary=extractive_summary(summary_raw),
                    url=getattr(e, "link", None),
                    tags=",".join(tag_news(title, summary_raw)),
                    published=getattr(e, "published_parsed", None),
                )
            )
    return rows


# Every NFL team -> a Google News query that surfaces beat writers, local
# newspapers, and press-conference coverage (which break role/injury news first).
NFL_TEAMS = [
    "Arizona Cardinals", "Atlanta Falcons", "Baltimore Ravens", "Buffalo Bills",
    "Carolina Panthers", "Chicago Bears", "Cincinnati Bengals", "Cleveland Browns",
    "Dallas Cowboys", "Denver Broncos", "Detroit Lions", "Green Bay Packers",
    "Houston Texans", "Indianapolis Colts", "Jacksonville Jaguars", "Kansas City Chiefs",
    "Las Vegas Raiders", "Los Angeles Chargers", "Los Angeles Rams", "Miami Dolphins",
    "Minnesota Vikings", "New England Patriots", "New Orleans Saints", "New York Giants",
    "New York Jets", "Philadelphia Eagles", "Pittsburgh Steelers", "San Francisco 49ers",
    "Seattle Seahawks", "Tampa Bay Buccaneers", "Tennessee Titans", "Washington Commanders",
]


def _google_news_url(team: str) -> str:
    from urllib.parse import quote_plus

    query = (
        f'"{team}" (injury OR practice OR "depth chart" OR "press conference" '
        f"OR snaps OR starting OR ruled OR questionable)"
    )
    return (
        "https://news.google.com/rss/search?q="
        + quote_plus(query)
        + "&hl=en-US&gl=US&ceid=US:en"
    )


def _publisher_from_entry(e, title: str) -> str:
    """Extract the underlying beat/local publisher from a Google News entry."""
    src = getattr(e, "source", None)
    if src is not None:
        name = getattr(src, "title", None) or (src.get("title") if isinstance(src, dict) else None)
        if name:
            return name
    # Google News titles end with " - Publisher".
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    return "Beat / Local"


def fetch_team_news(max_per_team: int = 5, teams: list[str] | None = None) -> list[NewsRow]:
    """Aggregate beat-writer / local / press-conference coverage per team."""
    import feedparser

    rows: list[NewsRow] = []
    for team in teams or NFL_TEAMS:
        try:
            with httpx.Client(timeout=8, headers=_UA, follow_redirects=True) as c:
                xml = c.get(_google_news_url(team)).text
            parsed = feedparser.parse(xml)
        except Exception:
            continue
        for e in parsed.entries[:max_per_team]:
            raw_title = getattr(e, "title", "") or ""
            publisher = _publisher_from_entry(e, raw_title)
            headline = raw_title.rsplit(" - ", 1)[0] if " - " in raw_title else raw_title
            summary_raw = getattr(e, "summary", "") or ""
            tags = tag_news(headline, summary_raw)
            tags.append("beat")
            rows.append(
                NewsRow(
                    source=f"{publisher} · {team}",
                    headline=headline[:390],
                    summary=extractive_summary(summary_raw),
                    url=getattr(e, "link", None),
                    tags=",".join(dict.fromkeys(tags)),
                    published=getattr(e, "published_parsed", None),
                )
            )
    return rows
