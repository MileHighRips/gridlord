# Operations & Production Guide

## Background workers

Heavy work (Monte Carlo sims, nightly ranking refresh, provider syncs) should run
off the request path.

- **Recommended:** Celery + Redis broker, or `arq`/`dramatiq` for async-native.
- **Simple start:** FastAPI `BackgroundTasks` + a cron container calling
  `POST /api/projections/refresh` nightly.

```
┌────────────┐   enqueue   ┌───────────┐   store    ┌────────────┐
│ API (FastAPI) ├──────────►│ Worker    ├───────────►│ Postgres    │
└────────────┘             │ (Celery)  │            │  + Redis    │
        ▲  cache hit       └───────────┘            └────────────┘
        └───────────────────────────────────────────────┘
```

## Caching strategy (Redis)

| Cached item | Key | TTL | Invalidation |
| --- | --- | --- | --- |
| Ranking board | `rank:{league_id}:{week}` | 6h | manual refresh, ADP delta ingest |
| Monte Carlo sim | `sim:{league_id}:{roster_hash}` | 12h | roster/transaction change |
| Mock-draft board | `mock:{league_id}` | 24h | ranking refresh |
| Provider league | `prov:{provider}:{league_id}` | 1h | webhook/poll event |

Always support a **manual refresh override** (`?force=true`) that bypasses cache
and re-warms it.

## Delta ingestion

Only fetch changed data:

- Track `updated_at` / provider ETags per resource.
- For ADP/injuries, diff against the last snapshot and upsert changed rows.
- Write an `AuditLog` row per ingest with the source list.

## Rate limiting & retries

- All provider adapters use `tenacity` exponential backoff (see
  `app/providers/*`).
- Add a token-bucket limiter per provider (`RateLimitPolicy` on the adapter).
- Respect `Retry-After` headers; never hammer a 429.

## Observability

- **Structured logs:** JSON logs (add `structlog`) with `request_id`, `league_id`.
- **Errors:** Sentry (`sentry-sdk[fastapi]`) — init in `main.py`.
- **Metrics:** Prometheus middleware; track p95 latency for `/draft/recommend`
  and `/lineup/optimize` against the 2s SLO.

## Security

- **App sessions:** JWT (`python-jose`), short-lived + refresh.
- **Provider OAuth:** store only necessary tokens (`ProviderToken`), encrypt at
  rest, expose a revoke endpoint/UI.
- **RBAC:** `role` on `User` (manager/commissioner/admin) gates settings writes.
- **Secrets:** environment only; never commit `.env`.

## Performance targets

| Operation | Target | How |
| --- | --- | --- |
| 1,000 mock drafts | < 60s | cached VORP board, no DB in loop |
| Lineup optimize | < 2s | cached weekly projections |
| 10k season sims | < 30s | vectorized NumPy, cache result |
| Daily refresh | nightly job | delta ingest + worker |

## Deploy (staging)

- **Backend:** container from `backend/Dockerfile` → Fly.io / Render / Railway.
- **Frontend:** `npm run build` → static host (Vercel/Netlify) with
  `VITE_API_BASE` pointed at the API.
- **DB:** managed Postgres; run `python -m app.seed` once to bootstrap.
- CI: `.github/workflows/ci.yml` runs tests + Prettier, then the deploy job.
