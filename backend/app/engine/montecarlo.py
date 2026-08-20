"""Monte Carlo season simulator (vectorized NumPy).

Given each team's starting-lineup weekly point distribution (mean, std) and a
round-robin schedule, simulate the regular season + playoffs `n_sims` times to
estimate: expected wins, playoff probability, and championship EV.

Performance: 10k sims for a 14-team league runs in well under 30s on a laptop
thanks to full vectorization over (sims x weeks x teams).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class TeamSeasonInput:
    team_id: int
    name: str
    weekly_mean: float
    weekly_std: float


@dataclass
class TeamSeasonResult:
    team_id: int
    name: str
    expected_wins: float
    playoff_prob: float
    championship_prob: float
    avg_points: float


def _round_robin(n: int, weeks: int) -> np.ndarray:
    """Return a (weeks, n) array of opponent indices via the circle method."""
    teams = list(range(n))
    if n % 2:  # odd -> add a bye placeholder
        teams.append(-1)
    m = len(teams)
    real_n = n
    schedule = []
    arr = teams[:]
    for _ in range(weeks):
        row = list(range(real_n))
        for i in range(m // 2):
            a, b = arr[i], arr[m - 1 - i]
            if a != -1 and b != -1:
                if a < real_n:
                    row[a] = b
                if b < real_n:
                    row[b] = a
            else:
                real = a if a != -1 else b
                if real < real_n:
                    row[real] = real  # bye -> plays self (no-op)
        schedule.append(row)
        arr = [arr[0]] + [arr[-1]] + arr[1:-1]  # rotate keeping first fixed
    return np.array(schedule)


def simulate_season(
    teams: list[TeamSeasonInput],
    regular_weeks: int = 14,
    playoff_teams: int = 6,
    n_sims: int = 10_000,
    seed: int | None = 42,
) -> list[TeamSeasonResult]:
    """Run the Monte Carlo season simulation."""
    rng = np.random.default_rng(seed)
    n = len(teams)
    if n < 2:
        return [
            TeamSeasonResult(t.team_id, t.name, 0.0, 0.0, 0.0, t.weekly_mean)
            for t in teams
        ]

    means = np.array([t.weekly_mean for t in teams])
    stds = np.array([max(t.weekly_std, 1.0) for t in teams])

    schedule = _round_robin(n, regular_weeks)  # (weeks, n)

    scores = rng.normal(
        loc=means[None, None, :],
        scale=stds[None, None, :],
        size=(n_sims, regular_weeks, n),
    )
    scores = np.clip(scores, 0, None)

    wins = np.zeros((n_sims, n))
    for w in range(regular_weeks):
        opp = schedule[w]  # (n,)
        my = scores[:, w, :]  # (n_sims, n)
        opp_scores = my[:, opp]
        played = opp != np.arange(n)
        wins += ((my > opp_scores) & played[None, :]).astype(float)

    total_points = scores.sum(axis=1)  # (n_sims, n)

    rank_key = wins + total_points * 1e-6
    order = np.argsort(-rank_key, axis=1)
    seeds = order[:, :playoff_teams]

    made_playoffs = np.zeros((n_sims, n), dtype=bool)
    rows = np.arange(n_sims)[:, None]
    made_playoffs[rows, seeds] = True

    champions = _simulate_bracket(seeds, means, stds, rng)

    results = []
    for i, t in enumerate(teams):
        results.append(
            TeamSeasonResult(
                team_id=t.team_id,
                name=t.name,
                expected_wins=round(float(wins[:, i].mean()), 2),
                playoff_prob=round(float(made_playoffs[:, i].mean()), 4),
                championship_prob=round(float((champions == i).mean()), 4),
                avg_points=round(float(total_points[:, i].mean()), 1),
            )
        )
    results.sort(key=lambda r: r.championship_prob, reverse=True)
    return results


def _simulate_bracket(
    seeds: np.ndarray, means: np.ndarray, stds: np.ndarray, rng: np.random.Generator
) -> np.ndarray:
    """Single-elimination among the seeded teams. Returns champion index per sim."""
    n_sims, k = seeds.shape
    size = 1
    while size < k:
        size *= 2
    field = np.zeros((n_sims, size), dtype=int)
    field[:, :k] = seeds
    if size > k:
        field[:, k:] = seeds[:, : size - k]  # byes -> top seeds advance (approx)

    current = field
    while current.shape[1] > 1:
        half = current.shape[1] // 2
        left = current[:, :half]
        right = current[:, half:][:, ::-1]  # 1v(n), 2v(n-1) style
        left_scores = rng.normal(means[left], np.maximum(stds[left], 1.0))
        right_scores = rng.normal(means[right], np.maximum(stds[right], 1.0))
        winners = np.where(left_scores >= right_scores, left, right)
        current = winners
    return current[:, 0]
