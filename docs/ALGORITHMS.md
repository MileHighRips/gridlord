# Algorithms & Analytics Methods

## 1. Scoring engine

Fully data-driven from the league's `scoring.rules`. Cumulative stats are
multiplied by their per-unit weight; event counts by their per-event weight.

**Yardage bonuses** (`bonus_<stat>_<threshold>`) are **non-cumulative** — only the
single highest reached threshold in each family is awarded (matches Yahoo).
DST **points-allowed** uses inclusive tier buckets.

See [backend/app/engine/scoring.py](../backend/app/engine/scoring.py).

## 2. Projection ensemble

For each player we blend multiple source projections (already scored to the
league):

$$\hat{p} = \sum_i w_i p_i,\qquad w_i = \frac{1/\text{MAE}_i}{\sum_j 1/\text{MAE}_j}$$

Weights come from each source's historical Mean Absolute Error (lower error →
higher weight; maintained in `projection_sources.accuracy_weight`).

The uncertainty band combines cross-source disagreement with an intrinsic
volatility floor:

$$\sigma = \sqrt{\underbrace{\sum_i w_i (p_i - \hat{p})^2}_{\text{disagreement}} + (\alpha\,\hat{p})^2}$$

Floor/ceiling are the ~15th/85th percentiles ($\hat{p} \pm 1.04\,\sigma$).

## 3. VORP rankings

$$\text{VORP}_p = \text{proj}_p - \text{replacement}_{\text{pos}(p)}$$

Replacement level = projected points of the $N$-th ranked player at the position,
where $N \approx \text{teams} \times \text{starters at position}$ (positional
scarcity). Tiers are formed by detecting larger-than-average VORP drop-offs.
Each ranking exposes its **top-3 drivers** for explainability.

## 4. Monte Carlo season simulation

Weekly team scores are drawn $s_{t,w} \sim \mathcal{N}(\mu_t, \sigma_t)$ (clipped
at 0), matched on a circle-method round robin. We tally wins, seed the top
`playoff_teams`, then simulate a single-elimination bracket with fresh weekly
draws. Aggregating over $n$ sims yields expected wins, playoff %, and
championship EV. Fully vectorized over `(sims × weeks × teams)`.

## 5. Live draft recommender

For the player pool minus drafted players:

1. **Need weighting:** `value = VORP × need_multiplier(position, roster_needs)`
   where FLEX-eligible surpluses absorb the FLEX slot.
2. **Survival probability** to your next pick (logistic on ADP slack vs. the
   number of intervening picks) — snake math computes your next overall pick.
3. **Scarcity alerts** when a needed position is about to fall off a talent
   cliff before your next pick.

See [backend/app/engine/draft_engine.py](../backend/app/engine/draft_engine.py).

## 6. Hidden-gem detection

$$\text{score} = (\text{proj} - \text{proj}_{\text{ADP}}) \times \text{usage\_trend} \times (1 - \text{rostered\_pct})$$

`proj_ADP` is a log-linear fit of projection vs. ADP (the "expected by draft
cost" baseline). Players well above their ADP tier, lightly rostered, and
trending up float to the top.

## 7. Trade analysis

Net VORP swing per side, ROS-points delta, positional-fit score, and a risk
score (mean coefficient of variation of incoming assets). A verdict blends net
VORP with positional fit; lopsided deals generate counteroffer suggestions.
