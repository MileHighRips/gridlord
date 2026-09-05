"""Live ingestion: pull real data and (re)build the player universe + rankings.

Run:  python -m app.ingest          # full live refresh
Also invoked by POST /api/projections/refresh-live.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime

from sqlalchemy.orm import Session

from .data_sources import (
    _availability,
    fetch_last_year_points,
    fetch_news,
    fetch_projection_rows,
    fetch_trending_adds,
    practice_status,
)
from .database import SessionLocal, init_db
from .engine.boombust import boom_bust
from .models import ADPEntry, AuditLog, NewsItem, Player, Projection, ProjectionSource


def _norm(name: str) -> str:
    """Normalize a player name for cross-source matching."""
    n = name.lower()
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", n)
    n = re.sub(r"[^a-z ]", "", n)
    return re.sub(r"\s+", " ", n).strip()


def _ensure_default_league(db: Session) -> None:
    """Create the default league + 14 teams (Conner @ slot 7) if none exists."""
    from .defaults import DEFAULT_LEAGUE
    from .models import League, Team
    from .services import create_league_from_settings

    if db.query(League).count() > 0:
        return
    league = create_league_from_settings(db, DEFAULT_LEAGUE)
    team_names = [f"Team {i}" for i in range(1, 15)]
    team_names[6] = "Conner"
    for i, name in enumerate(team_names, start=1):
        db.add(
            Team(league_id=league.id, name=name, owner=name,
                 draft_slot=i, is_me=(name == "Conner"))
        )
    db.flush()


def _match_player_by_name(db: Session, headline: str) -> Player | None:
    """Best-effort: link a news headline to a player by surname presence."""
    # Cheap heuristic: check the two capitalized tokens against known names.
    tokens = [t.strip(",.:;'\"") for t in headline.split() if t[:1].isupper()]
    if len(tokens) < 2:
        return None
    full = f"{tokens[0]} {tokens[1]}"
    return db.query(Player).filter(Player.name.ilike(f"%{full}%")).first()


def run_ingest(season: int = 2026, with_news: bool = True) -> dict:
    """Full live ingestion. Idempotent upsert keyed on sleeper_id."""
    init_db()
    db: Session = SessionLocal()
    started = time.perf_counter()
    try:
        _ensure_default_league(db)

        errors: list[str] = []

        source = (
            db.query(ProjectionSource)
            .filter(ProjectionSource.name == "Sleeper 2026")
            .first()
        )
        if not source:
            source = ProjectionSource(name="Sleeper 2026", accuracy_weight=1.0)
            db.add(source)
            db.flush()

        rows = _safe_fetch(lambda: fetch_projection_rows(season), [], "projections", errors)
        last_year = _safe_fetch(lambda: fetch_last_year_points(season - 1), {}, "last_year_stats", errors)
        trending = _safe_fetch(lambda: fetch_trending_adds(150), {}, "trending_adds", errors)

        # Clean up any duplicate player rows left by an interrupted or previously
        # concurrent ingest so the same player can never rank twice.
        _dedupe_players(db)

        # Collapse any duplicate incoming rows (same sleeper_id) to the highest
        # projection so a single upstream glitch cannot create a double entry.
        deduped: dict[str, "PlayerProjectionRow"] = {}
        for r in rows:
            prev = deduped.get(r.sleeper_id)
            if prev is None or r.mean_points > prev.mean_points:
                deduped[r.sleeper_id] = r
        rows = list(deduped.values())

        existing = {p.sleeper_id: p for p in db.query(Player).all() if p.sleeper_id}
        n_players = 0
        for r in rows:
            factor, _label = _availability(r.injury_status)
            ly = last_year.get(r.sleeper_id)

            player = existing.get(r.sleeper_id)
            if not player:
                player = Player(sleeper_id=r.sleeper_id)
                db.add(player)
                existing[r.sleeper_id] = player
            player.name = r.name
            player.position = r.position
            player.team = r.team
            player.years_exp = r.years_exp
            player.injury_status = r.injury_status
            player.injury_note = r.injury_note
            player.play_probability = round(factor, 2)
            player.last_year_points = ly
            player.active = True
            db.flush()

            # Projection (season / ROS = week 0). Injury-adjusted mean drives ranking.
            proj = (
                db.query(Projection)
                .filter(Projection.player_id == player.id, Projection.week == 0)
                .first()
            )
            if not proj:
                proj = Projection(player_id=player.id, week=0, season=season)
                db.add(proj)
            proj.source_id = source.id
            proj.mean_points = round(r.mean_points * factor, 1)
            proj.std_points = r.std_points
            proj.floor_points = round(proj.mean_points - 1.04 * r.std_points, 1)
            proj.ceiling_points = round(proj.mean_points + 1.04 * r.std_points, 1)
            proj.is_ensemble = True
            proj.raw_stats_json = json.dumps(r.raw_stats)

            # Boom/bust probability from the projection distribution.
            bb = boom_bust(proj.mean_points, r.std_points, r.position, games=17)
            proj.boom_pct = bb.boom_pct
            proj.bust_pct = bb.bust_pct

            # Depth-chart-driven volatility + a first-pass usage score.
            player.volatility_index = _volatility_from(r.position, r.std_points,
                                                       proj.mean_points)

            # ADP + rostered/pickup velocity.
            adp_row = (
                db.query(ADPEntry).filter(ADPEntry.player_id == player.id).first()
            )
            if not adp_row:
                adp_row = ADPEntry(player_id=player.id, source="sleeper", format="PPR")
                db.add(adp_row)
            adp_row.adp = r.adp if r.adp is not None else 999.0
            velocity = trending.get(r.sleeper_id, 0)
            # Rough rostered proxy: better ADP => more rostered.
            if r.adp:
                adp_row.rostered_pct = round(max(0.02, min(0.99, 1.15 - r.adp / 200.0)), 2)
            else:
                adp_row.rostered_pct = round(min(0.5, velocity / 20000.0), 3)
            n_players += 1

        n_news = 0
        if with_news:
            n_news = _ingest_news(db)

        # Expert consensus (FantasyPros) + analyst buzz (YouTube) enrichment.
        n_ecr = _enrich_fantasypros(db, season)
        n_buzz = _enrich_buzz(db)
        _compute_consensus(db)

        db.add(
            AuditLog(
                action="live_refresh",
                sources=(
                    "Sleeper 2026 projections, 2025 stats, trending; FantasyPros ECR; "
                    "YouTube analyst buzz (Flock/FantasyPros/Footballers/ETR/FBG/FantasyLife); "
                    "RSS news (PFT/PFF/ESPN/RotoWire/CBS/Yardbarker)"
                ),
                detail_json=(
                    f'{{"players": {n_players}, "news": {n_news}, '
                    f'"ecr_matched": {n_ecr}, "buzz_matched": {n_buzz}}}'
                ),
            )
        )
        db.commit()
        elapsed = round(time.perf_counter() - started, 2)

        live_players = n_players
        live_news = n_news

        # If the live sources returned nothing (blocked network, cold host, or a
        # rate-limited upstream), fall back to the player universe already in the
        # database so the app always reports usable rankings for offline
        # recommendations instead of a misleading zero -- but surface *why* the
        # live pull came back empty so the user can see the real reason.
        status = "ok"
        reason: str | None = None
        if live_players == 0:
            n_players = db.query(Player).filter(Player.active).count()
            n_news = db.query(NewsItem).count()
            status = "cached"
            reason = (
                "; ".join(errors)
                if errors
                else "Live sources returned no projection rows (upstream empty or rate-limited)."
            )

        return {
            "status": status,
            "players": n_players, "news": n_news,
            "live_players": live_players, "live_news": live_news,
            "ecr_matched": n_ecr, "buzz_matched": n_buzz,
            "reason": reason, "errors": errors,
            "elapsed_seconds": elapsed,
        }
    finally:
        db.close()


def _safe_fetch(fetcher, default, label: str = "", errors: list[str] | None = None):
    """Run an external fetch, returning a default if the upstream source fails.

    Live refreshes must never crash just because a scraper is rate-limited or the
    host has no outbound network; the app falls back to the seeded universe and
    records the failure reason so it can be reported to the user.
    """
    try:
        return fetcher()
    except Exception as exc:  # noqa: BLE001 - report the real upstream reason
        if errors is not None:
            errors.append(f"{label or 'source'}: {type(exc).__name__}: {exc}".strip())
        return default


def _dedupe_players(db: Session) -> int:
    """Deactivate duplicate player rows that share a normalized name + position.

    An interrupted or previously concurrent ingest could create two rows for the
    same player (e.g. two "Bijan Robinson" RBs). Keep the best-projected row (then
    the one with a sleeper_id) and deactivate the rest so a player never ranks
    twice. Returns the number of rows deactivated.
    """
    proj_by_player = {
        pr.player_id: pr.mean_points
        for pr in db.query(Projection).filter(Projection.week == 0).all()
    }
    groups: dict[tuple[str, str], list[Player]] = {}
    for p in db.query(Player).filter(Player.active).all():
        groups.setdefault((_norm(p.name), p.position), []).append(p)

    removed = 0
    for group in groups.values():
        if len(group) < 2:
            continue
        group.sort(
            key=lambda pl: (
                proj_by_player.get(pl.id, 0.0),
                1 if pl.sleeper_id else 0,
                pl.id,
            ),
            reverse=True,
        )
        for extra in group[1:]:
            extra.active = False
            removed += 1
    if removed:
        db.flush()
    return removed


def _volatility_from(position: str, std: float, mean: float) -> float:
    """0..100 volatility index from coefficient of variation."""
    cv = std / (mean + 1e-6)
    return round(min(cv * 180, 100), 1)


def _enrich_fantasypros(db: Session, season: int) -> int:
    """Match FantasyPros ECR to players; set ecr, disagreement, movement, boom/bust."""
    from .sources import FantasyProsSource

    try:
        rows = FantasyProsSource(year=season, scoring="PPR").fetch()
    except Exception:
        return 0
    index: dict[tuple[str, str], Player] = {}
    name_index: dict[str, Player] = {}
    for p in db.query(Player).filter(Player.active).all():
        index[(_norm(p.name), p.position)] = p
        name_index.setdefault(_norm(p.name), p)

    matched = 0
    for r in rows:
        key = (_norm(r.name), r.position)
        player = index.get(key) or name_index.get(_norm(r.name))
        if not player:
            continue
        player.ecr = r.rank
        player.ecr_std = r.rank_std
        player.ecr_delta = r.delta
        matched += 1
        # Refine boom/bust with expert disagreement.
        proj = (
            db.query(Projection)
            .filter(Projection.player_id == player.id, Projection.week == 0)
            .first()
        )
        if proj and r.rank_std:
            bb = boom_bust(proj.mean_points, proj.std_points, player.position,
                           games=17, expert_std=r.rank_std)
            proj.boom_pct = bb.boom_pct
            proj.bust_pct = bb.bust_pct
    db.flush()
    return matched


def _enrich_buzz(db: Session) -> int:
    """Pull analyst YouTube buzz; store as insight news + set usage/role signals."""
    from .scrapers import compute_player_buzz, fetch_youtube_insights

    try:
        insights = fetch_youtube_insights()
    except Exception:
        return 0
    players = db.query(Player).filter(Player.active).all()
    names = [p.name for p in players]
    buzz = compute_player_buzz(insights, names)
    by_name = {p.name: p for p in players}

    # Store insight videos as source-attributed news.
    for it in insights[:80]:
        db.add(
            NewsItem(
                player_id=None,
                source=it.source,
                headline=it.title[:390],
                summary=it.summary or None,
                url=it.url,
                tags="video," + it.sentiment,
                published_at=datetime.now(),
            )
        )

    matched = 0
    for name, b in buzz.items():
        player = by_name.get(name)
        if not player:
            continue
        matched += 1
        # Usage/buzz score blends mention velocity + net sentiment across analysts.
        net = b.riser_hits - b.faller_hits
        player.usage_score = round(
            min(100.0, b.mentions * 12 + max(net, 0) * 10 + len(b.sources) * 6), 1
        )
        if net > 0:
            player.role_note = f"📈 Analyst riser — {b.mentions} mentions across {len(b.sources)} shows"
        elif net < 0:
            player.role_note = f"📉 Analyst caution — {b.mentions} mentions across {len(b.sources)} shows"
        elif b.mentions:
            player.role_note = f"On analyst radar — {b.mentions} mentions"
    db.flush()
    return matched


def _compute_consensus(db: Session) -> None:
    """Blend Sleeper points-rank with FantasyPros ECR into a consensus rank."""
    players = db.query(Player).filter(Player.active).all()
    projs = {
        p.player_id: p.mean_points
        for p in db.query(Projection).filter(Projection.week == 0).all()
    }
    # Sleeper overall rank by projected points.
    ranked = sorted(players, key=lambda p: -(projs.get(p.id, 0.0)))
    sleeper_rank = {p.id: i + 1 for i, p in enumerate(ranked)}
    for p in players:
        s_rank = sleeper_rank.get(p.id, len(players))
        if p.ecr:
            p.consensus_rank = int(round(0.55 * s_rank + 0.45 * p.ecr))
        else:
            p.consensus_rank = s_rank
    db.flush()


def _ingest_news(db: Session) -> int:
    rows = fetch_news()
    # Add beat-writer / local / press-conference coverage (Google News per team).
    try:
        from .data_sources import fetch_team_news

        rows += fetch_team_news(max_per_team=4)
    except Exception:
        pass
    # Clear stale feed items (keep table small); keep last refresh only.
    db.query(NewsItem).delete()
    count = 0
    for r in rows:
        published = datetime.now()
        if r.published:
            try:
                published = datetime(*r.published[:6])
            except Exception:
                pass
        player = _match_player_by_name(db, r.headline)
        if player and "practice" in (r.tags or ""):
            ps = practice_status(f"{r.headline} {r.summary or ''}")
            if ps:
                player.practice_status = ps
        db.add(
            NewsItem(
                player_id=player.id if player else None,
                source=r.source,
                headline=r.headline,
                summary=r.summary,
                url=r.url,
                tags=r.tags,
                published_at=published,
            )
        )
        count += 1
    return count


if __name__ == "__main__":
    result = run_ingest()
    print(f"Live ingest complete: {result}")
