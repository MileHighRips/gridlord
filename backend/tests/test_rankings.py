"""Tests for the VORP ranking engine."""
from __future__ import annotations

from app.engine.rankings import PlayerProjection, rank_players


def _sample():
    players = []
    # 40 WRs descending, 40 RBs descending, some QBs.
    for i in range(40):
        players.append(
            PlayerProjection(i, f"WR{i}", "WR", "X", 260 - i * 3, 40, adp=i + 1)
        )
    for i in range(40):
        players.append(
            PlayerProjection(100 + i, f"RB{i}", "RB", "X", 270 - i * 4, 45, adp=i + 1.5)
        )
    for i in range(15):
        players.append(
            PlayerProjection(200 + i, f"QB{i}", "QB", "X", 330 - i * 2, 30, adp=i + 25)
        )
    return players


def test_rank_players_orders_by_vorp():
    ranked = rank_players(_sample())
    assert ranked[0].rank == 1
    # VORP should be monotonically non-increasing.
    vorps = [r.vorp for r in ranked]
    assert vorps == sorted(vorps, reverse=True)


def test_each_player_has_three_drivers():
    ranked = rank_players(_sample())
    for r in ranked[:20]:
        assert 1 <= len(r.drivers) <= 3


def test_positional_rank_assigned():
    ranked = rank_players(_sample())
    wr1 = next(r for r in ranked if r.position == "WR" and r.positional_rank == 1)
    assert wr1.name == "WR0"


def test_tiers_present():
    ranked = rank_players(_sample())
    assert max(r.tier for r in ranked) >= 2


def test_adp_delta_value_detection():
    ranked = rank_players(_sample())
    # Some player should register an ADP value/caution delta.
    assert any(r.adp_delta is not None for r in ranked)
