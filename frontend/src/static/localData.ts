// Static-mode data provider. When no backend API is reachable (e.g. the GitHub
// Pages PWA on a phone), the app reads the daily snapshot in /public/data and
// computes rankings, gems, draft recs, and scoring re-scores on-device. League
// settings persist in localStorage so scoring changes stick per device.
import type {
  BoardPlayer,
  DraftPickIn,
  DraftRecommendResponse,
  InjuryRow,
  IntelRow,
  LeagueSettings,
  NewsRow,
  RankingRow,
} from '../api/client';
import {
  computeDraftRecommend,
  computeGems,
  computeRankings,
  type StaticPlayer,
} from './engine';

const BASE = import.meta.env.BASE_URL || '/';
const SETTINGS_KEY = 'gridlord_settings';
const BOARD_KEY = 'gridlord_board';

let _players: StaticPlayer[] | null = null;
let _defaults: LeagueSettings | null = null;
let _news: NewsRow[] | null = null;
let _injuries: InjuryRow[] | null = null;
let _sim: { standings: Record<string, unknown>[] } | null = null;

async function loadJson<T>(name: string): Promise<T> {
  const res = await fetch(`${BASE}data/${name}`);
  if (!res.ok) throw new Error(`snapshot ${name} unavailable`);
  return res.json() as Promise<T>;
}

async function players(): Promise<StaticPlayer[]> {
  if (!_players) _players = await loadJson<StaticPlayer[]>('players.json');
  return _players;
}
async function defaults(): Promise<LeagueSettings> {
  if (!_defaults) _defaults = await loadJson<LeagueSettings>('defaults.json');
  return _defaults;
}

function storedSettings(): LeagueSettings | null {
  const raw = localStorage.getItem(SETTINGS_KEY);
  return raw ? (JSON.parse(raw) as LeagueSettings) : null;
}
async function settings(): Promise<LeagueSettings> {
  return storedSettings() ?? (await defaults());
}

async function rankings(position?: string): Promise<RankingRow[]> {
  const rows = computeRankings(await players(), await settings());
  const filtered = position ? rows.filter((r) => r.position === position) : rows;
  return position ? filtered.map((r, i) => ({ ...r, rank: i + 1 })) : filtered;
}

export const local = {
  isStatic: true,

  async rankings(position?: string): Promise<RankingRow[]> {
    return rankings(position);
  },

  async hiddenGems(): Promise<Record<string, unknown>[]> {
    return computeGems(await players(), await settings());
  },

  async news(tag?: string): Promise<NewsRow[]> {
    if (!_news) _news = await loadJson<NewsRow[]>('news.json');
    return tag ? _news.filter((n) => n.tags?.includes(tag)) : _news;
  },

  async injuries(): Promise<InjuryRow[]> {
    if (!_injuries) _injuries = await loadJson<InjuryRow[]>('injuries.json');
    return _injuries;
  },

  async playerIntel(sort: string): Promise<IntelRow[]> {
    const ps = await players();
    const ranked = new Map((await rankings()).map((r) => [r.player_id, r]));
    const rows: IntelRow[] = ps.map((p) => {
      const r = ranked.get(p.player_id);
      return {
        player_id: p.player_id,
        name: p.name,
        position: p.position,
        team: p.team,
        usage_score: p.usage_score,
        role_note: p.role_note,
        volatility_index: p.volatility_index,
        ecr: p.ecr,
        ecr_delta: p.ecr_delta,
        practice_status: p.practice_status,
        injury_status: p.injury_status,
        boom_pct: r?.boom_pct ?? null,
        bust_pct: r?.bust_pct ?? null,
        proj_points: r?.proj_points ?? null,
      };
    });
    const key = (r: IntelRow) =>
      sort === 'risers'
        ? (r.ecr_delta ?? -999)
        : sort === 'boom'
          ? (r.boom_pct ?? 0)
          : sort === 'bust'
            ? (r.bust_pct ?? 0)
            : (r.usage_score ?? 0);
    return rows
      .filter((r) => sort === 'usage' || key(r))
      .sort((a, b) => key(b) - key(a))
      .slice(0, 40);
  },

  async myLeague(): Promise<{ id: number; name: string; settings: LeagueSettings }> {
    const s = await settings();
    return { id: 1, name: s.leagueName, settings: s };
  },
  async defaults(): Promise<LeagueSettings> {
    return defaults();
  },
  async updateLeague(_id: number, s: LeagueSettings): Promise<unknown> {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
    return { ok: true };
  },
  async createLeague(s: LeagueSettings): Promise<{ id: number }> {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
    return { id: 1 };
  },

  async draftRecommend(state: {
    num_teams: number;
    rounds: number;
    my_slot: number;
    picks_made: DraftPickIn[];
    position_filter?: string[] | null;
  }): Promise<DraftRecommendResponse> {
    return computeDraftRecommend(state, await rankings());
  },

  async simulateSeason(): Promise<{ standings: Record<string, unknown>[] }> {
    if (!_sim)
      _sim = await loadJson<{ standings: Record<string, unknown>[] }>('sim.json');
    return _sim;
  },

  async getBoard(): Promise<{ saved: boolean; players: BoardPlayer[] }> {
    const raw = localStorage.getItem(BOARD_KEY);
    const rows = await rankings();
    if (raw) {
      const ids: number[] = JSON.parse(raw);
      const byId = new Map(rows.map((r) => [r.player_id, r]));
      const ordered = ids
        .map((id) => byId.get(id))
        .filter((r): r is RankingRow => !!r)
        .map((r) => ({
          player_id: r.player_id,
          name: r.name,
          position: r.position,
          team: r.team,
        }));
      return { saved: true, players: ordered };
    }
    return {
      saved: false,
      players: rows
        .slice(0, 200)
        .map((r) => ({
          player_id: r.player_id,
          name: r.name,
          position: r.position,
          team: r.team,
        })),
    };
  },
  async saveBoard(playerIds: number[]): Promise<{ status: string; count: number }> {
    localStorage.setItem(BOARD_KEY, JSON.stringify(playerIds));
    return { status: 'ok', count: playerIds.length };
  },
};
