// Typed API client for the GRIDLORD backend.
const BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';

const TOKEN_KEY = 'gridlord_token';
export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = tokenStore.get();
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json() as Promise<T>;
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
    request<RankingRow[]>(
      `/api/projections/rankings${position ? `?position=${position}` : ''}`,
    ),
  refreshRankings: () =>
    request<{ status: string; players_ranked: number; top_player: string }>(
      '/api/projections/refresh',
      { method: 'POST' },
    ),
  refreshLive: () =>
    request<{ status: string; players: number; news: number; elapsed_seconds: number }>(
      '/api/projections/refresh-live',
      { method: 'POST' },
    ),
  hiddenGems: () => request<Record<string, unknown>[]>('/api/projections/hidden-gems'),
  news: (tag?: string) => request<NewsRow[]>(`/api/news${tag ? `?tag=${tag}` : ''}`),
  injuries: () => request<InjuryRow[]>('/api/news/injuries'),
  defaults: () => request<LeagueSettings>('/api/leagues/defaults'),
  leagues: () =>
    request<Array<{ id: number; name: string; settings: LeagueSettings }>>(
      '/api/leagues',
    ),
  updateLeague: (id: number, settings: LeagueSettings) =>
    request(`/api/leagues/${id}`, {
      method: 'PUT',
      body: JSON.stringify(settings),
    }),
  createLeague: (settings: LeagueSettings) =>
    request<{ id: number }>('/api/leagues', {
      method: 'POST',
      body: JSON.stringify(settings),
    }),
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
    request<DraftRecommendResponse>('/api/draft/recommend', {
      method: 'POST',
      body: JSON.stringify(state),
    }),
  simulateSeason: (nSims = 5000) =>
    request<{ standings: Record<string, unknown>[] }>(
      `/api/projections/simulate-season?n_sims=${nSims}`,
      { method: 'POST' },
    ),
  sources: () =>
    request<{ live_count: number; pending_count: number; sources: SourceRow[] }>(
      '/api/sources',
    ),
  playerIntel: (sort = 'usage') =>
    request<IntelRow[]>(`/api/players/intel/board?sort=${sort}`),
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
    request<{ id: number; name: string; settings: LeagueSettings }>('/api/leagues/mine'),
  // Custom draft board
  getBoard: () => request<{ saved: boolean; players: BoardPlayer[] }>('/api/board'),
  saveBoard: (playerIds: number[], name = 'My Board') =>
    request<{ status: string; count: number }>('/api/board', {
      method: 'PUT',
      body: JSON.stringify({ player_ids: playerIds, name }),
    }),
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
