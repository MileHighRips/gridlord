// Typed API client for the GRIDLORD backend.
import { local } from '../static/localData';

const LOCAL_API_CANDIDATES = [
  'http://localhost:8000',
  'http://localhost:8001',
  'http://localhost:8002',
  'http://127.0.0.1:8000',
  'http://127.0.0.1:8001',
  'http://127.0.0.1:8002',
];

const API_BASE_KEY = 'gridlord_api_base';
const CACHE_VERSION_KEY = 'gridlord_cache_version';
const CACHE_VERSION = '2026-09-05-v2';
const REFRESH_LIVE_CACHE_KEY = 'gridlord_refresh_live_cache';
const CACHE_KEYS = {
  rankings: 'gridlord_rankings_cache',
  hiddenGems: 'gridlord_hidden_gems_cache',
  news: 'gridlord_news_cache',
  injuries: 'gridlord_injuries_cache',
};

function refreshCacheIfNeeded(): void {
  if (typeof window === 'undefined') return;
  const current = window.localStorage.getItem(CACHE_VERSION_KEY);
  if (current !== CACHE_VERSION) {
    Object.values(CACHE_KEYS).forEach((key) => window.localStorage.removeItem(key));
    window.localStorage.setItem(CACHE_VERSION_KEY, CACHE_VERSION);
  }
}

refreshCacheIfNeeded();

function getStoredApiBase(): string | null {
  if (typeof window === 'undefined') return null;
  const stored = window.localStorage.getItem(API_BASE_KEY)?.trim();
  if (!stored) return null;

  const normalized = stored.replace(/\/+$/, '');
  if (!normalized) return null;

  const lower = normalized.toLowerCase();
  if (lower.includes('localhost') || lower.includes('127.0.0.1')) {
    return null;
  }

  return normalized;
}

function persistApiBase(base: string): void {
  if (typeof window === 'undefined') return;
  const normalized = base.replace(/\/+$/, '');

  if (!normalized) return;
  window.localStorage.setItem(API_BASE_KEY, normalized);
}

export function resolveApiBase(): string {
  const configured = import.meta.env.VITE_API_BASE?.trim();
  if (configured) return configured.replace(/\/+$/, '');

  if (typeof window !== 'undefined') {
    const host = window.location.hostname.toLowerCase();
    if (host.includes('github.io')) return 'https://gridlord-api.onrender.com';
    if (host.includes('localhost') || host === '127.0.0.1') return LOCAL_API_CANDIDATES[0];
  }

  const stored = getStoredApiBase();
  if (stored) return stored;

  return 'https://gridlord-api.onrender.com';
}

let BASE = resolveApiBase();

const TOKEN_KEY = 'gridlord_token';

export async function fetchJson<T>(input: string, init?: RequestInit): Promise<T> {
  const res = await fetch(input, init);
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}${text ? `: ${text}` : ''}`);
  }

  if (!text) return undefined as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    return text as unknown as T;
  }
}
export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

async function request<T>(
  path: string,
  options?: RequestInit,
  timeoutMs = 8000,
): Promise<T> {
  const token = tokenStore.get();
  const candidates = Array.from(
    new Set([
      BASE,
      ...LOCAL_API_CANDIDATES.filter((candidate) => candidate !== BASE),
      ...(typeof window !== 'undefined' ? [getStoredApiBase() ?? ''] : []),
    ].filter(Boolean)),
  ) as string[];

  let lastError: Error | null = null;
  for (const base of candidates) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
      const res = await fetch(`${base}${path}`, {
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        signal: ctrl.signal,
        ...options,
      });
      if (res.ok) {
        BASE = base;
        persistApiBase(base);
        return res.json() as Promise<T>;
      }
      const text = await res.text();
      const err = new Error(`${res.status} ${res.statusText}: ${text}`);
      if (base.startsWith('http://localhost:') || base.startsWith('http://127.0.0.1:')) {
        lastError = err;
        continue;
      }
      throw err;
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));
      if (base === 'https://gridlord-api.onrender.com') {
        throw lastError;
      }
    } finally {
      clearTimeout(timer);
    }
  }

  throw lastError ?? new Error(`API request failed for ${path}`);
}

// Try the live API; if it's unreachable (e.g. static PWA on a phone), fall back
// to the on-device engine using the baked-in data snapshot.
function readCache<T>(key: string): T | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function writeCache<T>(key: string, value: T): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Ignore storage quota issues.
  }
}

function withFallback<T>(live: () => Promise<T>, fallback: () => Promise<T>): Promise<T> {
  return live().catch(fallback);
}

function withCache<T>(
  key: string,
  live: () => Promise<T>,
  fallback: () => Promise<T>,
): Promise<T> {
  return withFallback(
    async () => {
      const value = await live();
      writeCache(key, value);
      return value;
    },
    async () => {
      const cached = readCache<T>(key);
      if (cached !== null) return cached;
      return fallback();
    },
  );
}

export interface RankingRow {
  rank: number;
  player_id: number;
  name: string;
  position: string;
  team: string | null;
  proj_points: number;
  vorp: number;
  positional_rank: number;
  adp: number | null;
  adp_delta: number | null;
  volatility: number;
  upside_score: number;
  tier: number;
  drivers: string[];
  ecr?: number | null;
  ecr_delta?: number | null;
  boom_pct?: number | null;
  bust_pct?: number | null;
  consensus_rank?: number | null;
  adp_divergence?: number | null;
  usage_score?: number | null;
  role_note?: string | null;
}

export interface DraftPickIn {
  overall_pick: number;
  player_id: number;
  slot: number;
}

export interface DraftRecommendation {
  player_id: number;
  name: string;
  position: string;
  team: string | null;
  proj_points: number;
  vorp: number;
  need_weighted_value: number;
  adp: number | null;
  reach_risk: string;
  survival_probability: number;
  drivers: string[];
}

export interface DraftRecommendResponse {
  on_the_clock: boolean;
  your_next_overall_pick: number;
  picks_until_next: number;
  current_round: number;
  roster_needs: Record<string, number>;
  scarcity_alerts: string[];
  recommendations: DraftRecommendation[];
  best_available_by_position: Record<string, DraftRecommendation | null>;
  opponent_styles: {
    slot: number;
    style: string;
    roster: Record<string, number>;
    predicted_next: string;
  }[];
  predicted_picks: { overall: number; slot: number; predicted_position: string }[];
  positional_forecast: Record<
    string,
    {
      startable_now: number;
      expected_taken_before_you: number;
      likely_remaining: number;
      run_risk: string;
    }
  >;
}

export interface SourceRow {
  key: string;
  name: string;
  kind: string;
  available: boolean;
  weight: number;
  note: string;
}

export interface IntelRow {
  player_id: number;
  name: string;
  position: string;
  team: string | null;
  usage_score: number | null;
  role_note: string | null;
  volatility_index: number | null;
  ecr: number | null;
  ecr_delta: number | null;
  practice_status: string | null;
  injury_status: string | null;
  boom_pct: number | null;
  bust_pct: number | null;
  proj_points: number | null;
}

export interface NewsRow {
  id: number;
  headline: string;
  summary: string | null;
  url: string | null;
  source: string;
  tags: string[];
  player_id: number | null;
  player_name: string | null;
  published_at: string | null;
}

export interface InjuryRow {
  player_id: number;
  name: string;
  position: string;
  team: string | null;
  injury_status: string;
  note: string | null;
  play_probability: number | null;
}

export interface ScoringConfig {
  type: string;
  rules: Record<string, number>;
}

export interface LeagueSettings {
  leagueName: string;
  teams: number;
  season: number;
  scoring: ScoringConfig;
  roster: { starters: Record<string, number>; bench: number; ir_slots: number };
  waiver: {
    type: string;
    budget: number;
    reset: string;
    process_day: string;
    clear_days: number;
  };
  trades: {
    review: string;
    veto_votes: number;
    reject_days: number;
    deadline: string | null;
    allow_draft_pick_trades: boolean;
  };
  keepers: { count: number; cost_increase: string | null };
  playoff_teams: number;
  playoff_start_week: number;
  playoff_end_week: number;
  fractional_points: boolean;
  negative_points: boolean;
}

export const api = {
  health: () => request<{ status: string }>('/health'),
  rankings: (position?: string) =>
    withCache(
      `${CACHE_KEYS.rankings}${position ? `:${position}` : ''}`,
      () =>
        request<RankingRow[]>(
          `/api/projections/rankings${position ? `?position=${position}` : ''}`,
        ),
      () => local.rankings(position),
    ),
  refreshRankings: () =>
    request<{ status: string; players_ranked: number; top_player: string }>(
      '/api/projections/refresh',
      { method: 'POST' },
    ),
  refreshLive: async () => {
    try {
      const data = await request<{
        status: string;
        players: number;
        news: number;
        live_players?: number;
        live_news?: number;
        reason?: string | null;
        errors?: string[];
        elapsed_seconds: number;
      }>('/api/projections/refresh-live', { method: 'POST' }, 120000);

      if (typeof window !== 'undefined') {
        Object.values(CACHE_KEYS).forEach((key) => window.localStorage.removeItem(key));
        window.localStorage.setItem(CACHE_VERSION_KEY, CACHE_VERSION);
        writeCache(REFRESH_LIVE_CACHE_KEY, data);
      }
      return data;
    } catch (error) {
      throw new Error(
        error instanceof Error
          ? error.message
          : 'Live refresh failed and no reason was returned by the server.',
      );
    }
  },
  hiddenGems: () =>
    withCache(
      CACHE_KEYS.hiddenGems,
      () => request<Record<string, unknown>[]>('/api/projections/hidden-gems'),
      () => local.hiddenGems(),
    ),
  news: (tag?: string) =>
    withCache(
      `${CACHE_KEYS.news}${tag ? `:${tag}` : ''}`,
      () => request<NewsRow[]>(`/api/news${tag ? `?tag=${tag}` : ''}`),
      () => local.news(tag),
    ),
  injuries: () =>
    withCache(
      CACHE_KEYS.injuries,
      () => request<InjuryRow[]>('/api/news/injuries'),
      () => local.injuries(),
    ),
  defaults: () =>
    withFallback(
      () => request<LeagueSettings>('/api/leagues/defaults'),
      () => local.defaults(),
    ),
  leagues: () =>
    request<Array<{ id: number; name: string; settings: LeagueSettings }>>(
      '/api/leagues',
    ),
  updateLeague: (id: number, settings: LeagueSettings) =>
    withFallback(
      () =>
        request<{ id: number; name: string; settings: LeagueSettings }>(`/api/leagues/${id}`, {
          method: 'PUT',
          body: JSON.stringify(settings),
        }),
      () => local.updateLeague(id, settings) as Promise<{ id: number; name: string; settings: LeagueSettings }>,
    ),
  createLeague: (settings: LeagueSettings) =>
    withFallback(
      () =>
        request<{ id: number; name: string; settings: LeagueSettings }>('/api/leagues', {
          method: 'POST',
          body: JSON.stringify(settings),
        }),
      () => local.createLeague(settings) as Promise<{ id: number; name: string; settings: LeagueSettings }>,
    ),
  importLeague: (provider: string, leagueSettingsJson: unknown) =>
    request('/api/leagues/import', {
      method: 'POST',
      body: JSON.stringify({ provider, leagueSettingsJson }),
    }),
  draftRecommend: (state: {
    league_id: number;
    num_teams: number;
    rounds: number;
    my_slot: number;
    draft_type: string;
    picks_made: DraftPickIn[];
    position_filter?: string[] | null;
  }) =>
    withFallback(
      () =>
        request<DraftRecommendResponse>('/api/draft/recommend', {
          method: 'POST',
          body: JSON.stringify(state),
        }),
      () => local.draftRecommend(state),
    ),
  simulateSeason: (nSims = 5000) =>
    withFallback(
      () =>
        request<{ standings: Record<string, unknown>[] }>(
          `/api/projections/simulate-season?n_sims=${nSims}`,
          { method: 'POST' },
        ),
      () => local.simulateSeason(),
    ),
  sources: () =>
    request<{ live_count: number; pending_count: number; sources: SourceRow[] }>(
      '/api/sources',
    ),
  playerIntel: (sort = 'usage') =>
    withFallback(
      () => request<IntelRow[]>(`/api/players/intel/board?sort=${sort}`),
      () => local.playerIntel(sort),
    ),
  // Auth
  register: (email: string, password: string) =>
    request<AuthOut>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  login: (email: string, password: string) =>
    request<AuthOut>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<{ id: number; email: string; role: string }>('/api/auth/me'),
  myLeague: () =>
    withFallback(
      () =>
        request<{ id: number; name: string; settings: LeagueSettings }>(
          '/api/leagues/mine',
        ),
      () => local.myLeague(),
    ),
  // Custom draft board
  getBoard: () =>
    withFallback(
      () => request<{ saved: boolean; players: BoardPlayer[] }>('/api/board'),
      () => local.getBoard(),
    ),
  saveBoard: (playerIds: number[], name = 'My Board') =>
    withFallback(
      () =>
        request<{ status: string; count: number }>('/api/board', {
          method: 'PUT',
          body: JSON.stringify({ player_ids: playerIds, name }),
        }),
      () => local.saveBoard(playerIds),
    ),
};

export interface AuthOut {
  access_token: string;
  token_type: string;
  email: string;
  role: string;
}

export interface BoardPlayer {
  player_id: number;
  name: string;
  position: string;
  team: string | null;
}
