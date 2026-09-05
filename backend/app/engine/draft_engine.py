"""Draft engine: snake math, live recommendations, and mock-draft simulation.

The live recommender answers, on every pick:
- Who is the best available for **your** exact league scoring (VORP-ranked)?
- Which pick is best given the roster you have already built (need weighting)?
- How likely is a target to survive to your next pick (scarcity/ADP model)?
- How many picks until you're on the clock again (snake math)?
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .rankings import RankedPlayer


# Starter targets for the default league (14-team). Used for roster-need weighting.
DEFAULT_STARTER_NEEDS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "DEF": 1}
FLEX_ELIGIBLE = {"RB", "WR", "TE"}

# Roster construction targets: (starters, ideal_total_incl_bench). Drives depth
# weighting so the engine stops hammering a position once it's built out.
ROSTER_TARGETS = {
    "QB": (1, 2),
    "RB": (2, 5),   # 2 starters + flex + bench depth (RB attrition is high)
    "WR": (2, 6),   # 2 starters + flex + bench depth
    "TE": (1, 2),
    "K": (1, 1),
    "DEF": (1, 1),
}
FLEX_SLOTS = 1


@dataclass
class DraftContext:
    num_teams: int
    rounds: int
    my_slot: int  # 1-based
    draft_type: str = "snake"


@dataclass
class Recommendation:
    player: RankedPlayer
    need_weighted_value: float
    survival_probability: float
    reach_risk: str
    drivers: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Snake-draft math
# --------------------------------------------------------------------------- #
def overall_picks_for_slot(
    slot: int, num_teams: int, rounds: int, snake: bool = True
) -> list[int]:
    """All overall pick numbers owned by a given 1-based slot."""
    picks = []
    for rnd in range(1, rounds + 1):
        if snake and rnd % 2 == 0:
            pick_in_round = num_teams - slot + 1
        else:
            pick_in_round = slot
        picks.append((rnd - 1) * num_teams + pick_in_round)
    return picks


def slot_for_overall(overall: int, num_teams: int, snake: bool = True) -> int:
    """Return the slot that owns a given 1-based overall pick."""
    rnd = (overall - 1) // num_teams + 1
    pos_in_round = (overall - 1) % num_teams + 1
    if snake and rnd % 2 == 0:
        return num_teams - pos_in_round + 1
    return pos_in_round


def next_pick_for_slot(
    slot: int, num_teams: int, rounds: int, picks_made: int, snake: bool = True
) -> int | None:
    """Next overall pick for `slot` given how many picks have already been made."""
    for overall in overall_picks_for_slot(slot, num_teams, rounds, snake):
        if overall > picks_made:
            return overall
    return None


# --------------------------------------------------------------------------- #
# Roster need
# --------------------------------------------------------------------------- #
def roster_needs(
    my_positions: list[str], starter_needs: dict[str, int] | None = None
) -> dict[str, int]:
    """Remaining starter slots to fill, accounting for FLEX absorption."""
    starter_needs = starter_needs or DEFAULT_STARTER_NEEDS
    counts: dict[str, int] = {}
    for pos in my_positions:
        counts[pos] = counts.get(pos, 0) + 1

    needs: dict[str, int] = {}
    flex_pool = 0
    for pos, need in starter_needs.items():
        if pos == "FLEX":
            continue
        have = counts.get(pos, 0)
        needs[pos] = max(need - have, 0)
        if pos in FLEX_ELIGIBLE and have > need:
            flex_pool += have - need

    needs["FLEX"] = max(starter_needs.get("FLEX", 0) - flex_pool, 0)
    return needs


def _need_multiplier(position: str, needs: dict[str, int]) -> float:
    """Boost players at positions we still need; damp positions already filled."""
    direct = needs.get(position, 0)
    flex_contrib = needs.get("FLEX", 0) if position in FLEX_ELIGIBLE else 0
    unmet = direct + 0.5 * flex_contrib
    if unmet >= 2:
        return 1.35
    if unmet == 1:
        return 1.15
    if direct == 0 and flex_contrib == 0:
        return 0.75  # positional surplus
    return 1.0


def position_value_multiplier(
    position: str,
    my_positions: list[str],
    current_round: int,
    total_rounds: int,
    starter_needs: dict[str, int] | None = None,
) -> tuple[float, str]:
    """Roster-construction-aware multiplier + a short reason.

    This is the draft engine's pro-strategy knob: custom league starters are
    respected, early-round roster pressure is amplified, and K/DEF are suppressed
    until the final rounds. That is what makes a true pro draft feel like an
    actual draft board instead of a generic ranked list.
    """
    starter_needs = starter_needs or DEFAULT_STARTER_NEEDS
    counts: dict[str, int] = {}
    for p in my_positions:
        counts[p] = counts.get(p, 0) + 1
    have = counts.get(position, 0)
    starters = starter_needs.get(position, 0) or 1
    target_total = max(ROSTER_TARGETS.get(position, (1, 2))[1], starters)

    # Flex accounting: surplus RB/WR/TE beyond their starter counts feed FLEX.
    flex_surplus = sum(
        max(counts.get(p, 0) - max(starter_needs.get(p, 0), 1), 0) for p in FLEX_ELIGIBLE
    )
    flex_open = max(starter_needs.get("FLEX", 0) - flex_surplus, 0)

    # K / DEF: near-worthless until the last 3 rounds, then must-fill.
    rounds_left = total_rounds - current_round + 1
    if position in ("K", "DEF"):
        if have >= 1:
            return 0.05, f"{position} already rostered"
        if rounds_left <= 2:
            return 1.4, f"Last-rounds {position} fill"
        if rounds_left <= 4:
            return 0.6, f"{position} can wait 1–2 rounds"
        return 0.08, f"Too early for {position}"

    unmet = max(starters - have, 0)
    early_pressure = 0.0
    if current_round <= 3:
        early_pressure = 0.45
    elif current_round <= 6:
        early_pressure = 0.25
    elif current_round <= 10:
        early_pressure = 0.1

    # Starter slot still open at this position -> highest priority.
    if have < starters:
        urgency = 1.35 + unmet * 0.45 + early_pressure
        if position == "QB":
            urgency += 0.15
        if position in ("RB", "WR"):
            urgency += 0.1
        return round(urgency, 2), f"Fills {position}{have + 1} starter slot"

    # Starters filled; if FLEX is still open, depth is still useful.
    if position in FLEX_ELIGIBLE and flex_open > 0 and have < target_total:
        flex_value = 1.1 + early_pressure * 0.75
        return round(flex_value, 2), f"Depth for FLEX / bye coverage ({position}{have + 1})"

    # Building bench depth below target.
    if have < target_total:
        frac = (target_total - have) / max(target_total - starters, 1)
        depth_value = 0.7 + 0.35 * frac + max(0.0, 0.2 - (current_round / 20.0))
        return round(depth_value, 2), f"{position} bench depth ({have + 1})"

    # At or beyond target depth -> strongly discount.
    return 0.25, f"{position} already deep — value pick only"


# --------------------------------------------------------------------------- #
# Survival probability (will a player last to my next pick?)
# --------------------------------------------------------------------------- #
def survival_probability(
    adp: float | None, my_next_overall: int | None, picks_between: int
) -> float:
    """Logistic model: P(available) drops as ADP approaches the intervening picks."""
    if adp is None or my_next_overall is None:
        return 0.5
    slack = adp - (my_next_overall - picks_between)
    k = 0.45
    x = slack - picks_between
    return round(1.0 / (1.0 + math.exp(-k * x)), 3)


def _reach_risk(adp: float | None, current_overall: int) -> str:
    if adp is None:
        return "unknown"
    delta = current_overall - adp  # positive => picking earlier than ADP (a reach)
    if delta <= 6:
        return "safe"
    if delta <= 18:
        return "slight_reach"
    return "reach"


def _scarcity_multiplier(
    position: str,
    available: list[RankedPlayer],
    starter_needs: dict[str, int],
    roster_needs: dict[str, int],
    current_round: int,
) -> float:
    """Higher scarcity = stronger premium in the early/mid rounds."""
    pos_pool = [p for p in available if p.position == position]
    pos_candidates = [p for p in pos_pool if p.vorp > 0]
    count = len(pos_candidates)
    need_left = roster_needs.get(position, 0)
    slots_needed = max(starter_needs.get(position, 0), 1)

    if count == 0:
        return 1.0

    if position in ("RB", "WR"):
        if count <= 5:
            return 1.45
        if count <= 10:
            return 1.2
        if count <= 18:
            return 1.08
    if position == "QB":
        if count <= 8:
            return 1.35
        if count <= 14:
            return 1.15
    if position == "TE":
        if count <= 6:
            return 1.3
        if count <= 10:
            return 1.15
    if position in ("K", "DEF"):
        if count <= 2:
            return 1.2

    if need_left > 0 and current_round <= 8:
        return 1.15 + min(need_left, 2) * 0.12
    if slots_needed >= 2 and current_round <= 5:
        return 1.08
    return 1.0


def _round_timing_multiplier(position: str, current_round: int, total_rounds: int) -> float:
    """Concentrate value at the draft windows where that position matters most."""
    rounds_left = max(total_rounds - current_round + 1, 1)
    if position in ("RB", "WR"):
        if current_round <= 3:
            return 1.22
        if current_round <= 7:
            return 1.1
        if current_round <= 11:
            return 1.02
    if position == "QB":
        if current_round <= 4:
            return 1.12
        if current_round <= 9:
            return 1.05
        if rounds_left <= 3:
            return 1.08
    if position == "TE":
        if current_round <= 5:
            return 1.18
        if current_round <= 9:
            return 1.08
    if position in ("K", "DEF"):
        if rounds_left <= 3:
            return 1.35
        return 0.55
    return 1.0


def _championship_strategy_multiplier(
    position: str,
    my_positions: list[str],
    starter_needs: dict[str, int],
    current_round: int,
) -> float:
    """The final pro-draft layer: optimize for a title-contending roster build."""
    counts: dict[str, int] = {}
    for pos in my_positions:
        counts[pos] = counts.get(pos, 0) + 1

    need_gap = max((starter_needs.get(position, 0) or 1) - counts.get(position, 0), 0)
    flex_gap = max(
        starter_needs.get("FLEX", 0)
        - max(0, counts.get("RB", 0) - (starter_needs.get("RB", 0) or 1))
        - max(0, counts.get("WR", 0) - (starter_needs.get("WR", 0) or 1))
        - max(0, counts.get("TE", 0) - (starter_needs.get("TE", 0) or 1)),
        0,
    )

    base = 1.0
    if need_gap > 0:
        base += 0.45 * need_gap
    if position in FLEX_ELIGIBLE and flex_gap > 0:
        base += 0.24
    if position in ("RB", "WR") and current_round <= 6:
        base += 0.35
    if position == "QB" and current_round <= 4:
        base += 0.18
    if position == "TE" and current_round <= 6:
        base += 0.18
    if position in ("K", "DEF"):
        return 0.7
    return round(base, 3)


# --------------------------------------------------------------------------- #
# Live recommendation
# --------------------------------------------------------------------------- #
def recommend(
    available: list[RankedPlayer],
    ctx: DraftContext,
    picks_made: int,
    my_positions: list[str],
    starter_needs: dict[str, int] | None = None,
    top_n: int = 8,
    position_filter: list[str] | None = None,
) -> tuple[list[Recommendation], dict]:
    """Produce ranked live recommendations plus draft-state metadata."""
    starter_needs = starter_needs or DEFAULT_STARTER_NEEDS
    needs = roster_needs(my_positions, starter_needs)
    current_overall = picks_made + 1
    snake = ctx.draft_type.lower() == "snake"
    my_next = next_pick_for_slot(
        ctx.my_slot, ctx.num_teams, ctx.rounds, picks_made, snake
    )
    on_the_clock = my_next == current_overall
    picks_until_next = 0 if my_next is None else max(my_next - current_overall, 0)
    current_round = (picks_made // ctx.num_teams) + 1
    if snake and current_overall > 0:
        current_round = ((current_overall - 1) // ctx.num_teams) + 1

    pool = available
    if position_filter:
        pool = [p for p in pool if p.position in position_filter]

    recs: list[Recommendation] = []
    for p in pool:
        mult, reason = position_value_multiplier(
            p.position,
            my_positions,
            current_round,
            ctx.rounds,
            starter_needs=starter_needs,
        )
        scarce = _scarcity_multiplier(p.position, pool, starter_needs, needs, current_round)
        timing = _round_timing_multiplier(p.position, current_round, ctx.rounds)
        strategy = _championship_strategy_multiplier(
            p.position, my_positions, starter_needs, current_round
        )
        surv = survival_probability(p.adp, my_next, picks_until_next)
        risk = _reach_risk(p.adp, current_overall)

        # Pro-strategy composite: value + roster need + scarcity + timing + survival.
        late_round_bias = 1.0 if current_round <= 12 else 0.94
        championship_bias = 1.0 + max(0.0, strategy - 1.0) * 0.8
        safety_bonus = 1.0 + (0.18 if risk == "safe" else 0.09 if risk == "slight_reach" else 0.0)
        nwv = round(
            p.vorp * mult * scarce * timing * strategy * championship_bias * late_round_bias * (0.75 + 0.5 * surv) * safety_bonus,
            2,
        )

        drivers = list(p.drivers[:1])
        drivers.append(reason)
        if strategy > 1.3:
            drivers.append("Championship build: this pick aligns with your title-winning roster plan")
        if p.adp is not None and my_next:
            drivers.append(
                f"ADP {p.adp:.0f}; ~{surv:.0%} chance to survive to pick {my_next}"
            )
        recs.append(
            Recommendation(
                player=p,
                need_weighted_value=nwv,
                survival_probability=surv,
                reach_risk=risk,
                drivers=drivers[:3],
            )
        )

    recs.sort(key=lambda r: -r.need_weighted_value)

    scarcity_alerts = _scarcity_alerts(pool, needs, picks_until_next)

    meta = {
        "on_the_clock": on_the_clock,
        "your_next_overall_pick": my_next or 0,
        "picks_until_next": picks_until_next,
        "current_round": current_round,
        "roster_needs": needs,
        "scarcity_alerts": scarcity_alerts,
    }
    return recs[:top_n], meta


def _scarcity_alerts(
    pool: list[RankedPlayer], needs: dict[str, int], picks_until_next: int
) -> list[str]:
    """Warn when a needed position is about to fall off a talent cliff."""
    alerts: list[str] = []
    for pos, need in needs.items():
        if pos == "FLEX" or need <= 0:
            continue
        starters_left = [p for p in pool if p.position == pos and p.vorp > 0]
        likely_gone = min(len(starters_left), max(picks_until_next // 2, 0))
        remaining_after = len(starters_left) - likely_gone
        if 0 < remaining_after <= 3:
            alerts.append(
                f"Only ~{remaining_after} startable {pos}s likely to survive to your next pick"
            )
    return alerts


# --------------------------------------------------------------------------- #
# Mock draft simulation (for strategy testing / performance target)
# --------------------------------------------------------------------------- #
def simulate_mock_draft(
    board: list[RankedPlayer],
    ctx: DraftContext,
    adp_noise: float = 6.0,
    seed: int | None = None,
    starter_needs: dict[str, int] | None = None,
) -> list[tuple[int, RankedPlayer]]:
    """Simulate one full mock draft; opponents pick by ADP + gaussian noise."""
    import random

    rng = random.Random(seed)
    total = ctx.num_teams * ctx.rounds
    available = {p.player_id: p for p in board}
    my_positions: list[str] = []
    result: list[tuple[int, RankedPlayer]] = []

    for overall in range(1, total + 1):
        rnd = (overall - 1) // ctx.num_teams + 1
        pos_in_round = (overall - 1) % ctx.num_teams + 1
        slot = pos_in_round if rnd % 2 == 1 else ctx.num_teams - pos_in_round + 1

        pool = list(available.values())
        if not pool:
            break
        if slot == ctx.my_slot:
            pick = max(
                pool,
                key=lambda p: p.vorp
                * position_value_multiplier(
                    p.position,
                    my_positions,
                    rnd,
                    ctx.rounds,
                    starter_needs=starter_needs,
                )[0],
            )
            my_positions.append(pick.position)
        else:
            def key(p: RankedPlayer) -> float:
                base = p.adp if p.adp is not None else p.rank
                return base + rng.gauss(0, adp_noise)

            pick = min(pool, key=key)
        del available[pick.player_id]
        result.append((overall, pick))
    return result


# --------------------------------------------------------------------------- #
# Opponent modeling + positional scarcity forecast
# --------------------------------------------------------------------------- #
def _slot_for_overall(overall: int, num_teams: int, snake: bool = True) -> int:
    rnd = (overall - 1) // num_teams + 1
    pir = (overall - 1) % num_teams + 1
    if snake and rnd % 2 == 0:
        return num_teams - pir + 1
    return pir


def _predict_next_position(counts: dict[str, int], rounds_done: int) -> str:
    """Predict a slot's next position from what they've built (roster targets)."""
    best, best_score = "RB", -1.0
    for pos, (starters, total) in ROSTER_TARGETS.items():
        have = counts.get(pos, 0)
        need = max(starters - have, 0) * 2.0 + max(total - have, 0) * 0.3
        if pos in ("K", "DEF"):
            need = 0.05 if rounds_done < 12 else 3.0  # late only
        if need > best_score:
            best, best_score = pos, need
    return best


def draft_intel(
    picks_with_pos: list[dict],
    available: list[RankedPlayer],
    num_teams: int,
    rounds: int,
    my_slot: int,
    current_overall: int,
    my_next_overall: int | None,
    snake: bool = True,
) -> dict:
    """Opponent tendencies + predicted upcoming picks + positional run forecast."""
    # Build each slot's positional counts so far.
    tendencies: dict[int, dict[str, int]] = {}
    for pk in picks_with_pos:
        tendencies.setdefault(pk["slot"], {})
        tendencies[pk["slot"]][pk["position"]] = (
            tendencies[pk["slot"]].get(pk["position"], 0) + 1
        )

    # Human-readable opponent style labels.
    styles: list[dict] = []
    for slot, counts in sorted(tendencies.items()):
        if slot == my_slot:
            continue
        rb, wr = counts.get("RB", 0), counts.get("WR", 0)
        qb, te = counts.get("QB", 0), counts.get("TE", 0)
        if rb >= 2 and wr == 0:
            style = "RB-heavy"
        elif wr >= 2 and rb == 0:
            style = "Zero-RB"
        elif qb >= 1 and sum(counts.values()) <= 3:
            style = "Early-QB"
        elif te >= 1 and sum(counts.values()) <= 3:
            style = "Early-TE"
        else:
            style = "Balanced"
        rounds_done = sum(counts.values())
        styles.append(
            {
                "slot": slot,
                "style": style,
                "roster": counts,
                "predicted_next": _predict_next_position(counts, rounds_done),
            }
        )

    # Predict picks between now and your next selection; tally position demand.
    predictions: list[dict] = []
    expected_taken: dict[str, float] = {}
    sim_counts = {s: dict(c) for s, c in tendencies.items()}
    if my_next_overall:
        for overall in range(current_overall, my_next_overall):
            slot = _slot_for_overall(overall, num_teams, snake)
            if slot == my_slot:
                continue
            counts = sim_counts.setdefault(slot, {})
            pos = _predict_next_position(counts, sum(counts.values()))
            counts[pos] = counts.get(pos, 0) + 1
            expected_taken[pos] = expected_taken.get(pos, 0.0) + 1
            predictions.append({"overall": overall, "slot": slot, "predicted_position": pos})

    # Positional run forecast: startable now vs likely gone before your pick.
    forecast: dict[str, dict] = {}
    for pos in ("QB", "RB", "WR", "TE"):
        startable = [a for a in available if a.position == pos and a.vorp > 0]
        taken = expected_taken.get(pos, 0.0)
        remaining = max(len(startable) - taken, 0.0)
        run_risk = "high" if remaining <= 2 else ("medium" if remaining <= 4 else "low")
        forecast[pos] = {
            "startable_now": len(startable),
            "expected_taken_before_you": round(taken, 1),
            "likely_remaining": round(remaining, 1),
            "run_risk": run_risk,
        }

    return {
        "opponent_styles": styles,
        "predicted_picks": predictions,
        "positional_forecast": forecast,
    }
