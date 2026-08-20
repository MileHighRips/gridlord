"""Tests for projection normalization and ensemble modeling."""
from __future__ import annotations

from app.engine.projections import (
    SourceProjection,
    ensemble_projection,
    normalize_zscores,
    update_source_weights,
)


def test_ensemble_weighted_mean():
    sources = [
        SourceProjection("A", points=200, weight=0.6),
        SourceProjection("B", points=180, weight=0.4),
    ]
    r = ensemble_projection(sources)
    # 200*0.6 + 180*0.4 = 192
    assert abs(r.mean - 192.0) < 0.01
    assert r.contributing_sources == 2
    assert r.floor < r.mean < r.ceiling


def test_ensemble_empty():
    r = ensemble_projection([])
    assert r.mean == 0.0 and r.contributing_sources == 0


def test_disagreement_widens_band():
    tight = ensemble_projection(
        [SourceProjection("A", 200), SourceProjection("B", 201)]
    )
    wide = ensemble_projection(
        [SourceProjection("A", 150), SourceProjection("B", 250)]
    )
    assert wide.std > tight.std


def test_zscore_normalization():
    z = normalize_zscores({1: 100.0, 2: 200.0, 3: 300.0})
    assert abs(z[2]) < 1e-9  # middle value is the mean -> z ~ 0
    assert z[1] < 0 < z[3]


def test_source_weights_favor_accuracy():
    weights = update_source_weights({"good": 2.0, "bad": 8.0})
    assert weights["good"] > weights["bad"]
    assert abs(sum(weights.values()) - 1.0) < 1e-9
