# API Reference

Base URL (dev): `http://localhost:8000` · Interactive docs: `/docs` (Swagger) and `/redoc`.

All request/response bodies are JSON. Full OpenAPI schema is auto-generated at
`/openapi.json`.

---

## Leagues

### `GET /api/leagues/defaults`

Returns the canonical default league ("The League", 14-team PPR + bonuses).

```bash
curl http://localhost:8000/api/leagues/defaults
```

### `POST /api/leagues/import`

Import a league from any platform and auto-map fields to the internal model.

```bash
curl -X POST http://localhost:8000/api/leagues/import \
  -H "Content-Type: application/json" \
  -d @backend/examples/league_custom_bonus.json.wrapped
```

Body:

```json
{ "provider": "sleeper", "leagueSettingsJson": { "...": "raw league json" } }
```

Response:

```json
{
  "league": { "id": 2, "name": "...", "settings": { "...": "..." } },
  "mapping_accuracy": 0.95,
  "warnings": [],
  "unmapped_fields": []
}
```

### `POST /api/leagues` · `GET /api/leagues` · `GET /api/leagues/{id}` · `GET /api/leagues/{id}/export`

Manual create, list, fetch, and export the canonical settings JSON.

---

## Players

### `GET /api/players?position=RB&q=chase&limit=50`

List/search players.

### `GET /api/players/{id}`

Player detail: projection, ADP, and recent news.

---

## Projections & Rankings

### `GET /api/projections/rankings?position=WR&limit=200`

Explainable rankings. Each row includes `vorp`, `tier`, `adp_delta`, `volatility`,
`upside_score`, and a `drivers` array (top-3 reasons).

### `POST /api/projections/refresh`

Recompute rankings and write an audit-log entry (sources used).

### `GET /api/projections/hidden-gems`

Undervalued players (projection-vs-ADP delta, low rostered %).

### `POST /api/projections/simulate-season?n_sims=10000`

Monte Carlo season sim → per-team expected wins, playoff %, championship %.

---

## Draft (Live Assistant)

### `POST /api/draft/recommend`

The core live-draft endpoint. Send your slot + every pick made so far.

```bash
curl -X POST http://localhost:8000/api/draft/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "league_id": 1,
    "num_teams": 14,
    "rounds": 16,
    "my_slot": 7,
    "draft_type": "snake",
    "picks_made": [
      {"overall_pick": 1, "player_id": 1, "slot": 1},
      {"overall_pick": 2, "player_id": 2, "slot": 2}
    ]
  }'
```

Response highlights: `recommendations[]` (need-weighted, with `survival_probability`
and `drivers`), `roster_needs`, `scarcity_alerts`, `picks_until_next`,
`best_available_by_position`.

### `POST /api/draft/mock?n_sims=1000&my_slot=7`

Run N mock drafts; returns a sample roster + timing (perf target: 1k < 60s).

---

## Lineup / Trades / Waivers

### `POST /api/lineup/optimize`

```json
{ "player_ids": [1, 2, 3], "slots": ["QB","RB","RB","WR","WR","TE","FLEX","K","DEF"] }
```

### `POST /api/trades/analyze`

```json
{ "team_a_gives": [1], "team_b_gives": [5, 12], "team_a_needs": ["WR"] }
```

### `POST /api/waivers/recommend`

```json
{ "faab_budget": 100, "faab_remaining": 62, "my_needs": ["RB"] }
```

---

## Sync (cross-platform)

### `GET /api/sync/providers`

Lists available adapters and which support writes.

### `POST /api/sync/league` · `/api/sync/roster` · `/api/sync/transactions`

```json
{ "provider": "sleeper", "league_id": "123456789" }
```
