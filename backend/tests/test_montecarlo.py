"""Tests for the Monte Carlo season simulator and draft snake math."""
from __future__ import annotations

from app.engine.draft_engine import (
    DraftContext,
    next_pick_for_slot,
    overall_picks_for_slot,
    position_value_multiplier,
    roster_needs,
    survival_probability,
)
from app.engine.montecarlo import TeamSeasonInput, simulate_season


def test_snake_pick_math_slot1():
    picks = overall_picks_for_slot(1, num_teams=14, rounds=3)
    assert picks == [1, 28, 29]  # 1, then wheel at 28/29


def test_snake_pick_math_slot7_of_14():
    picks = overall_picks_for_slot(7, num_teams=14, rounds=2)
    assert picks[0] == 7
    assert picks[1] == 22  # round 2 reverse: 14-7+1=8 -> 14+8=22


def test_next_pick_after_made():
    nxt = next_pick_for_slot(7, num_teams=14, rounds=16, picks_made=7)
    assert nxt == 22


def test_roster_needs_flex_absorption():
    # Two RBs + two WRs fill RB2/WR2; a 3rd RB should feed FLEX.
    needs = roster_needs(["RB", "RB", "RB", "WR", "WR"])
    assert needs["RB"] == 0
    assert needs["WR"] == 0
    assert needs["FLEX"] == 0  # surplus RB absorbed the flex
    assert needs["QB"] == 1


def test_survival_probability_bounds():
    p = survival_probability(adp=50, my_next_overall=20, picks_between=13)
    assert 0.0 <= p <= 1.0


def test_simulate_season_probabilities_sum():
    teams = [
        TeamSeasonInput(i, f"T{i}", weekly_mean=110 + i, weekly_std=20)
        for i in range(14)
    ]
    results = simulate_season(teams, regular_weeks=14, playoff_teams=6, n_sims=1000)
    champ_total = sum(r.championship_prob for r in results)
    playoff_total = sum(r.playoff_prob for r in results)
    assert abs(champ_total - 1.0) < 0.05  # someone wins each sim
    assert abs(playoff_total - 6.0) < 0.1  # exactly 6 make playoffs
    # Stronger teams should have higher championship odds on average.
    assert results[0].championship_prob >= results[-1].championship_prob


def test_draft_context_dataclass():
    ctx = DraftContext(num_teams=14, rounds=16, my_slot=7)
    assert ctx.draft_type == "snake"


def test_position_value_multiplier_uses_league_roster_needs_and_round_pressure():
    custom = {"QB": 1, "RB": 3, "WR": 3, "TE": 1, "FLEX": 1, "K": 1, "DEF": 1}

    rb_mult, _ = position_value_multiplier("RB", ["QB", "WR"], 3, 16, starter_needs=custom)
    qb_mult, _ = position_value_multiplier("QB", ["RB", "WR"], 3, 16, starter_needs=custom)
    k_mult, _ = position_value_multiplier("K", ["RB", "WR"], 3, 16, starter_needs=custom)

    assert rb_mult > 1.4
    assert qb_mult > 1.0
    assert k_mult < 0.5
