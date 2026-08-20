"""Service layer: translate between the canonical settings schema and ORM rows."""
from __future__ import annotations

from sqlalchemy.orm import Session

from .models import League, LeagueSettings, RosterSlot, ScoringRule
from .schemas.league import (
    KeeperRules,
    LeagueSettingsIn,
    RosterConfig,
    ScoringConfig,
    TradeRules,
    WaiverRules,
)

# Scoring keys that are actually bonus/threshold rules -> (stat, threshold).
_BONUS_PREFIXES = ("bonus_pass_yd_", "bonus_rush_yd_", "bonus_rec_yd_")

_DST_STATS = {
    "sack", "def_int", "fum_rec", "def_td", "safety",
    "block_kick", "def_return_td", "xp_returned",
}


def persist_scoring_rules(db: Session, league_id: int, rules: dict[str, float]) -> None:
    """Insert ScoringRule rows for a league from a flat scoring dict."""
    for stat, points in rules.items():
        min_value = None
        canonical_stat = stat
        for prefix in _BONUS_PREFIXES:
            if stat.startswith(prefix):
                canonical_stat = prefix[:-1]  # e.g. "bonus_rush_yd"
                min_value = float(stat[len(prefix):])
                break
        applies = "K" if stat.startswith(("fg_", "pat_")) else (
            "DST" if stat in _DST_STATS else "OFF"
        )
        db.add(
            ScoringRule(
                league_id=league_id, stat=canonical_stat, points=points,
                min_value=min_value, applies_to=applies,
            )
        )


def create_league_from_settings(db: Session, settings: LeagueSettingsIn) -> League:
    """Persist a full league from the canonical settings payload."""
    league = League(
        name=settings.leagueName,
        provider="manual",
        season=settings.season,
        num_teams=settings.teams,
        scoring_type=settings.scoring.type,
    )
    db.add(league)
    db.flush()

    db.add(
        LeagueSettings(
            league_id=league.id,
            bench_size=settings.roster.bench,
            ir_slots=settings.roster.ir_slots,
            waiver_type=settings.waiver.type,
            faab_budget=settings.waiver.budget,
            waiver_reset=settings.waiver.reset,
            waiver_process_day=settings.waiver.process_day,
            waiver_clear_days=settings.waiver.clear_days,
            trade_review=settings.trades.review,
            trade_veto_votes=settings.trades.veto_votes,
            trade_reject_days=settings.trades.reject_days,
            trade_deadline=settings.trades.deadline,
            allow_draft_pick_trades=settings.trades.allow_draft_pick_trades,
            keeper_count=settings.keepers.count,
            keeper_cost_rule=settings.keepers.cost_increase,
            playoff_teams=settings.playoff_teams,
            playoff_start_week=settings.playoff_start_week,
            playoff_end_week=settings.playoff_end_week,
            fractional_points=settings.fractional_points,
            negative_points=settings.negative_points,
        )
    )

    for pos, count in settings.roster.starters.items():
        db.add(RosterSlot(league_id=league.id, position=pos, count=count))

    persist_scoring_rules(db, league.id, settings.scoring.rules)

    db.commit()
    db.refresh(league)
    return league


def league_to_settings(league: League) -> LeagueSettingsIn:
    """Rebuild the canonical settings payload from ORM rows."""
    s = league.settings
    starters = {slot.position: slot.count for slot in league.roster_slots}
    rules: dict[str, float] = {}
    for rule in league.scoring_rules:
        key = (
            f"{rule.stat}_{int(rule.min_value)}"
            if rule.min_value is not None
            else rule.stat
        )
        # Reconstruct bonus_ prefix for threshold rules.
        if rule.min_value is not None and rule.stat.startswith("bonus_"):
            key = f"{rule.stat}_{int(rule.min_value)}"
        rules[key] = rule.points

    return LeagueSettingsIn(
        leagueName=league.name,
        teams=league.num_teams,
        season=league.season,
        scoring=ScoringConfig(type=league.scoring_type, rules=rules),
        roster=RosterConfig(
            starters=starters,
            bench=s.bench_size if s else 6,
            ir_slots=s.ir_slots if s else 2,
        ),
        waiver=WaiverRules(
            type=s.waiver_type, budget=s.faab_budget, reset=s.waiver_reset,
            process_day=s.waiver_process_day, clear_days=s.waiver_clear_days,
        ) if s else WaiverRules(),
        trades=TradeRules(
            review=s.trade_review, veto_votes=s.trade_veto_votes,
            reject_days=s.trade_reject_days, deadline=s.trade_deadline,
            allow_draft_pick_trades=s.allow_draft_pick_trades,
        ) if s else TradeRules(),
        keepers=KeeperRules(count=s.keeper_count, cost_increase=s.keeper_cost_rule)
        if s else KeeperRules(),
        playoff_teams=s.playoff_teams if s else 6,
        playoff_start_week=s.playoff_start_week if s else 15,
        playoff_end_week=s.playoff_end_week if s else 17,
        fractional_points=s.fractional_points if s else True,
        negative_points=s.negative_points if s else True,
    )
