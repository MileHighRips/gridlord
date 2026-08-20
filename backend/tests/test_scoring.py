"""Unit tests for the scoring engine using the user's league defaults."""
from __future__ import annotations

from app.engine.scoring import (
    DEFAULT_SCORING,
    points_allowed_score,
    score_stat_line,
)


def test_ppr_reception_and_yardage():
    # 5 catches, 80 rec yds, 1 rec TD -> 5 + 8 + 6 = 19, plus 75-yd bonus (+3).
    line = {"receptions": 5, "rec_yd": 80, "rec_td": 1}
    result = score_stat_line(line)
    assert result.components["reception"] == 5.0
    assert result.components["rec_yd"] == 8.0
    assert result.components["rec_td"] == 6.0
    # 80 >= 75 threshold -> +3 bonus (not 100).
    assert result.components["bonus_rec_yd_75"] == 3.0
    assert result.total == 22.0


def test_bonus_uses_highest_single_threshold():
    # 160 rush yds should award only the 150 bonus (+7), not stacked bonuses.
    line = {"rush_yd": 160}
    result = score_stat_line(line)
    assert result.components["bonus_rush_yd_150"] == 7.0
    assert "bonus_rush_yd_100" not in result.components
    # 16.0 from yardage + 7 bonus = 23.0
    assert result.total == 23.0


def test_passing_with_interceptions_negative():
    line = {"pass_yd": 300, "pass_td": 2, "interception": 2}
    result = score_stat_line(line)
    assert result.components["pass_yd"] == 12.0  # 300 * 0.04
    assert result.components["pass_td"] == 8.0
    assert result.components["interception"] == -8.0  # 2 * -4
    assert result.components["bonus_pass_yd_300"] == 7.0
    assert result.total == 19.0


def test_kicker_distance_buckets():
    line = {"fg_40_49": 1, "fg_50_plus": 1, "pat_made": 3}
    result = score_stat_line(line)
    assert result.components["fg_40_49"] == 4.0
    assert result.components["fg_50_plus"] == 5.0
    assert result.components["pat_made"] == 3.0
    assert result.total == 12.0


def test_dst_points_allowed_tiers():
    assert points_allowed_score(0) == 10.0
    assert points_allowed_score(3) == 7.0
    assert points_allowed_score(13) == 4.0
    assert points_allowed_score(24) == 0.0
    assert points_allowed_score(40) == -4.0


def test_dst_full_line():
    line = {"sack": 3, "def_int": 2, "def_td": 1, "points_allowed": 10}
    result = score_stat_line(line)
    assert result.components["sack"] == 3.0
    assert result.components["def_int"] == 4.0
    assert result.components["def_td"] == 6.0
    assert result.components["points_allowed"] == 4.0  # 7-13 tier
    assert result.total == 17.0


def test_fractional_toggle():
    line = {"rec_yd": 55}  # 5.5 pts
    assert score_stat_line(line, fractional=True).total == 5.5
    assert score_stat_line(line, fractional=False).total == 6.0


def test_default_scoring_matches_league():
    assert DEFAULT_SCORING["reception"] == 1.0
    assert DEFAULT_SCORING["interception"] == -4.0
    assert DEFAULT_SCORING["rush_td"] == 6.0
    assert DEFAULT_SCORING["pass_yd"] == 0.04
