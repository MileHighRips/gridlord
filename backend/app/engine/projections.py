"""Projection ingestion + ensemble modeling.

Pipeline
--------
1. Ingest raw projections from multiple sources (points already scored to the
   league via :mod:`app.engine.scoring`).
2. Normalize each source to a common scale (z-score within position).
3. Ensemble: weighted mean where weights = historical source accuracy.
4. Derive uncertainty band (std), floor (~15th pct) and ceiling (~85th pct).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class SourceProjection:
    source: str
    points: float
    weight: float = 1.0  # historical accuracy weight in (0, 1]


@dataclass
class EnsembleResult:
    mean: float
    std: float
    floor: float
    ceiling: float
    contributing_sources: int
    per_source: dict[str, float] = field(default_factory=dict)


def ensemble_projection(
    sources: list[SourceProjection],
    volatility_floor: float = 0.12,
) -> EnsembleResult:
    """Combine multiple source projections into a weighted ensemble.

    The weighted mean uses source-accuracy weights. Disagreement between
    sources contributes to the uncertainty band, with a floor so that even
    unanimous sources retain realistic week-to-week variance.
    """
    if not sources:
        return EnsembleResult(0.0, 0.0, 0.0, 0.0, 0)

    pts = np.array([s.points for s in sources], dtype=float)
    wts = np.array([max(s.weight, 1e-6) for s in sources], dtype=float)
    wts = wts / wts.sum()

    mean = float(np.sum(pts * wts))

    var_between = float(np.sum(wts * (pts - mean) ** 2))
    std = float(np.sqrt(var_between + (volatility_floor * mean) ** 2))

    floor = max(0.0, mean - 1.04 * std)
    ceiling = mean + 1.04 * std

    return EnsembleResult(
        mean=round(mean, 2),
        std=round(std, 2),
        floor=round(floor, 2),
        ceiling=round(ceiling, 2),
        contributing_sources=len(sources),
        per_source={s.source: s.points for s in sources},
    )


def normalize_zscores(points_by_player: dict[int, float]) -> dict[int, float]:
    """Return z-scored points for a group (e.g. one position) for fair blending."""
    if not points_by_player:
        return {}
    vals = np.array(list(points_by_player.values()), dtype=float)
    mu, sigma = float(vals.mean()), float(vals.std() or 1.0)
    return {pid: (v - mu) / sigma for pid, v in points_by_player.items()}


def update_source_weights(mae_by_source: dict[str, float]) -> dict[str, float]:
    """Convert historical MAE into normalized weights (lower MAE -> higher weight)."""
    if not mae_by_source:
        return {}
    inv = {s: 1.0 / (mae + 1e-6) for s, mae in mae_by_source.items()}
    total = sum(inv.values())
    return {s: v / total for s, v in inv.items()}
