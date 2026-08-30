// Client-side ranking + scoring + draft engine — a faithful port of the Python
// engine (app/engine + app/rescore + app/data_sources). It lets the GitHub Pages
// PWA compute rankings, hidden gems, and live-draft recs entirely on-device from
// the static players.json snapshot, so scoring changes and the draft assistant
// work with no backend.
import type {
  DraftPickIn,
  DraftRecommendResponse,
  LeagueSettings,
  RankingRow,
} from '../api/client';

export interface StaticPlayer {
  player_id: number;
  name: string;
  position: string;
  team: string | null;
  bye_week: number | null;
  ecr: number | null;
  ecr_delta: number | null;
  adp: number | null;
  rostered_pct: number | null;
  injury_status: string | null;
  play_probability: number | null;
  last_year_points: number | null;
  usage_score: number | null;
  role_note: string | null;
  volatility_index: number | null;
  practice_status: string | null;
  raw_stats: Record<string, number>;
}

// --- scoring (mirror app/engine/scoring.DEFAULT_SCORING) --------------------
const POS_CV: Record<string, number> = {
  QB: 0.2,
  RB: 0.3,
  WR: 0.3,
  TE: 0.33,
  K: 0.24,
  DEF: 0.3,
};
const CV_PASS = 0.32;
const CV_RUSH = 0.55;
const CV_REC = 0.55;
const PASS_BONUS: [number, number][] = [
  [200, 3],
  [250, 5],
  [300, 7],
];
const RUSH_BONUS: [number, number][] = [
  [75, 3],
  [100, 5],
  [150, 7],
];
const REC_BONUS = RUSH_BONUS;

// Injury factor is precomputed server-side into play_probability, so the client
// just multiplies each player's base points by it.
const MARKET_WITHIN_POS = 0.7;

function normCdf(x: number): number {
  // Abramowitz-Stegun erf approximation.
  const t = 1 / (1 + 0.3275911 * Math.abs(x / Math.SQRT2));
  const y =
    1 -
    ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t +
      0.254829592) *
      t *
      Math.exp((-x * x) / 2);
  const erf = x < 0 ? -y : y;
  return 0.5 * (1 + erf);
}

function bonus(totalYd: number, gp: number, tiers: [number, number][], cv: number): number {
  if (gp <= 0 || totalYd <= 0) return 0;
  const perGame = totalYd / gp;
  const sd = Math.max(cv * perGame, 1);
  let prev = 0;
  let exp = 0;
  for (const [t, pts] of tiers) {
    const p = 1 - normCdf((t - perGame) / sd);
    exp += (pts - prev) * p;
    prev = pts;
  }
  return exp * gp;
}

function bonusTiers(scoring: Record<string, number>, prefix: string): [number, number][] {
  const out: [number, number][] = [];
  for (const [k, v] of Object.entries(scoring)) {
    if (k.startsWith(prefix)) {
      const n = Number(k.slice(prefix.length));
      if (!Number.isNaN(n)) out.push([n, v]);
    }
  }
  return out.sort((a, b) => a[0] - b[0]);
}

function w(scoring: Record<string, number>, key: string, dflt: number): number {
  return scoring[key] ?? dflt;
}

function scoreOffense(s: Record<string, number>, sc: Record<string, number>): number {
  let base = 0;
  base += (s.pass_yd || 0) * w(sc, 'pass_yd', 0.04);
  base += (s.pass_td || 0) * w(sc, 'pass_td', 4);
  base += (s.pass_int || 0) * w(sc, 'interception', -4);
  base += (s.rush_yd || 0) * w(sc, 'rush_yd', 0.1);
  base += (s.rush_td || 0) * w(sc, 'rush_td', 6);
  base += (s.rec || 0) * w(sc, 'reception', 1);
  base += (s.rec_yd || 0) * w(sc, 'rec_yd', 0.1);
  base += (s.rec_td || 0) * w(sc, 'rec_td', 6);
  base += (s.fum_lost || 0) * w(sc, 'fumble_lost', -2);
  const twoPt = (s.pass_2pt || 0) + (s.rush_2pt || 0) + (s.rec_2pt || 0);
  base += twoPt * w(sc, 'two_pt', 2);
  const gp = s.gp || 17;
  const hasBonus = Object.keys(sc).some((k) => k.startsWith('bonus_'));
  const passT = bonusTiers(sc, 'bonus_pass_yd_');
  const rushT = bonusTiers(sc, 'bonus_rush_yd_');
  const recT = bonusTiers(sc, 'bonus_rec_yd_');
  const pT = passT.length ? passT : hasBonus ? [] : PASS_BONUS;
  const ruT = rushT.length ? rushT : hasBonus ? [] : RUSH_BONUS;
  const reT = recT.length ? recT : hasBonus ? [] : REC_BONUS;
  const b =
    bonus(s.pass_yd || 0, gp, pT, CV_PASS) +
    bonus(s.rush_yd || 0, gp, ruT, CV_RUSH) +
    bonus(s.rec_yd || 0, gp, reT, CV_REC);
  return base + b;
}

function scoreKicker(s: Record<string, number>): number {
  const ptsStd = s.pts_std || 0;
  const long = (s.fgm_40_49 || 0) * 3 + (s.fgm_50p || 0) * 5 + (s.xpm || 0);
  const short = Math.max(0, (ptsStd - long) / 3);
  return (
    short * 3 +
    (s.fgm_40_49 || 0) * 4 +
    (s.fgm_50p || 0) * 5 +
    (s.xpm || 0) -
    (s.fgmiss_40_49 || 0) * 3 -
    (s.fgmiss_50p || 0) * 3 -
    (s.xpmiss || 0)
  );
}

const PA_TIERS: [string, number][] = [
  ['pts_allow_0', 10],
  ['pts_allow_1_6', 7],
  ['pts_allow_7_13', 4],
  ['pts_allow_14_20', 1],
  ['pts_allow_21_27', 0],
  ['pts_allow_28_34', -1],
  ['pts_allow_35p', -4],
];

function scoreDefense(s: Record<string, number>): number {
  let pts =
    (s.sack || 0) * 1 +
    (s.int || 0) * 2 +
    (s.fum_rec || 0) * 2 +
    (s.def_fum_td || 0) * 6 +
    (s.def_kr_td || 0) * 6 +
    (s.blk_kick || 0) * 3;
  for (const [key, val] of PA_TIERS) pts += (s[key] || 0) * val;
  return pts;
}

function scorePlayer(p: StaticPlayer, sc: Record<string, number>): number {
  if (p.position === 'K') return scoreKicker(p.raw_stats);
  if (p.position === 'DEF') return scoreDefense(p.raw_stats);
  return scoreOffense(p.raw_stats, sc);
}

// --- league-size VORP context (mirror engine/league_context) ---------------
const FLEX_ELIGIBLE = new Set(['RB', 'WR', 'TE']);

function replacementRanks(numTeams: number, starters: Record<string, number>) {
  const flex = (starters.FLEX || 0) + (starters['W/R/T'] || 0);
  const superflex = (starters.SUPERFLEX || 0) + (starters.SUPER_FLEX || 0);
  const share: Record<string, number> = { RB: 0, WR: 0, TE: 0, QB: 0 };
  if (flex) {
    share.RB += flex * 0.45;
    share.WR += flex * 0.45;
    share.TE += flex * 0.1;
  }
  if (superflex) {
    share.QB += superflex * 0.85;
    share.RB += superflex * 0.05;
    share.WR += superflex * 0.1;
  }
  const repl: Record<string, number> = {};
  for (const pos of ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']) {
    const base = (starters[pos] || 0) + (share[pos] || 0);
    const buffer = FLEX_ELIGIBLE.has(pos) ? Math.floor(numTeams / 2) : 2;
    repl[pos] = Math.max(Math.round(numTeams * base) + buffer, numTeams);
  }
  return repl;
}

// --- boom/bust (mirror engine/boombust) ------------------------------------
const BOOM: Record<string, number> = { QB: 24, RB: 20, WR: 20, TE: 14, K: 12, DEF: 12 };
const BUST: Record<string, number> = { QB: 14, RB: 8, WR: 8, TE: 6, K: 4, DEF: 3 };

function boomBust(mean: number, std: number, pos: string, expertStd: number | null) {
  const wm = mean / 17;
  let ws = Math.max(std / Math.sqrt(17), 1);
  if (expertStd) ws *= 1 + Math.min(expertStd / 20, 0.6);
  const boomT = BOOM[pos] ?? 18;
  const bustT = BUST[pos] ?? 8;
  const boom = (1 - normCdf((boomT - wm) / ws)) * 100;
  const bust = normCdf((bustT - wm) / ws) * 100;
  return { boom_pct: Math.round(boom * 10) / 10, bust_pct: Math.round(bust * 10) / 10 };
}

// --- main ranking (mirror engine/rankings.rank_players) --------------------
export function computeRankings(
  players: StaticPlayer[],
  settings: LeagueSettings,
): RankingRow[] {
  const sc = settings.scoring.rules;
  const repl = replacementRanks(settings.teams, settings.roster.starters);

  type E = {
    p: StaticPlayer;
    proj: number;
    std: number;
    vorp: number;
    posRank: number;
    blended: number;
    tier: number;
    boom: number;
    bust: number;
  };

  const rows: E[] = players.map((p) => {
    const base = scorePlayer(p, sc);
    const factor = p.play_probability ?? 1;
    const proj = Math.max(0, base * factor);
    const std = base * (POS_CV[p.position] ?? 0.3);
    const bb = boomBust(proj, std, p.position, p.ecr ? 3 : null);
    return {
      p,
      proj,
      std,
      vorp: 0,
      posRank: 0,
      blended: 0,
      tier: 1,
      boom: bb.boom_pct,
      bust: bb.bust_pct,
    };
  });

  // Replacement level = proj of the Nth-best at each position.
  const byPos: Record<string, E[]> = {};
  for (const e of rows) (byPos[e.p.position] ??= []).push(e);
  const replLevel: Record<string, number> = {};
  for (const [pos, group] of Object.entries(byPos)) {
    const sorted = [...group].sort((a, b) => b.proj - a.proj);
    const idx = Math.min((repl[pos] ?? group.length) - 1, group.length - 1);
    replLevel[pos] = sorted[Math.max(idx, 0)]?.proj ?? 0;
    sorted.forEach((e, i) => (e.posRank = i + 1));
  }
  for (const e of rows) e.vorp = e.proj - (replLevel[e.p.position] ?? 0);

  // Within-position expert-consensus ordering; VORP magnitudes set placement.
  for (const group of Object.values(byPos)) {
    const vorpsDesc = group.map((e) => e.vorp).sort((a, b) => b - a);
    const haveEcr = group.filter((e) => e.p.ecr != null).sort((a, b) => a.p.ecr! - b.p.ecr!);
    const noEcr = group.filter((e) => e.p.ecr == null).sort((a, b) => b.vorp - a.vorp);
    [...haveEcr, ...noEcr].forEach((e, i) => {
      const marketVorp = vorpsDesc[i];
      const wgt = e.p.ecr != null ? MARKET_WITHIN_POS : 0;
      e.blended = (1 - wgt) * e.vorp + wgt * marketVorp;
    });
  }

  rows.sort((a, b) => b.blended - a.blended);

  // Tiers from VORP gaps.
  assignTiers(rows);

  return rows.map((e, i) => {
    const rank = i + 1;
    const adpDelta = e.p.adp != null ? Math.round((e.p.adp - rank) * 10) / 10 : null;
    const adpDiv =
      e.p.adp != null && e.p.ecr != null ? Math.round((e.p.adp - e.p.ecr) * 10) / 10 : null;
    return {
      rank,
      player_id: e.p.player_id,
      name: e.p.name,
      position: e.p.position,
      team: e.p.team,
      proj_points: Math.round(e.proj * 10) / 10,
      vorp: Math.round(e.vorp * 10) / 10,
      positional_rank: e.posRank,
      adp: e.p.adp,
      adp_delta: adpDelta,
      volatility: Math.round((e.std / (e.proj + 1e-6)) * 1000) / 1000,
      upside_score: Math.round(e.std * 1.04 * 100) / 100,
      tier: e.tier,
      drivers: buildDrivers(e.p, e.vorp, e.posRank, e.proj, adpDelta),
      ecr: e.p.ecr,
      ecr_delta: e.p.ecr_delta,
      boom_pct: e.boom,
      bust_pct: e.bust,
      consensus_rank: null,
      adp_divergence: adpDiv,
      usage_score: e.p.usage_score,
      role_note: e.p.role_note,
    };
  });
}

function assignTiers(rows: { vorp: number; tier: number }[]): void {
  if (!rows.length) return;
  const order = [...rows].sort((a, b) => b.vorp - a.vorp);
  const diffs: number[] = [];
  for (let i = 0; i < order.length - 1; i++) diffs.push(order[i].vorp - order[i + 1].vorp);
  const pos = diffs.filter((d) => d > 0);
  const avg = pos.length ? pos.reduce((a, b) => a + b, 0) / pos.length : 1e-9;
  let tier = 1;
  order[0].tier = 1;
  for (let i = 1; i < order.length; i++) {
    if (order[i - 1].vorp - order[i].vorp > avg * 1.75) tier++;
    order[i].tier = tier;
  }
}

function buildDrivers(
  p: StaticPlayer,
  vorp: number,
  posRank: number,
  proj: number,
  adpDelta: number | null,
): string[] {
  const d = [
    `+${vorp.toFixed(1)} VORP over ${p.position} replacement`,
    `${p.position}${posRank} in projected points (${proj.toFixed(1)})`,
  ];
  if (p.injury_status && (p.play_probability ?? 1) < 0.95)
    d.splice(1, 0, `⚠ ${p.injury_status} — projection discounted for availability`);
  if (p.ecr) {
    if (p.ecr_delta && Math.abs(p.ecr_delta) >= 2)
      d.push(`Experts: ECR ${p.ecr.toFixed(0)} (${p.ecr_delta > 0 ? '▲ rising' : '▼ falling'} ${Math.abs(p.ecr_delta).toFixed(0)})`);
    else d.push(`Expert consensus ECR ${p.ecr.toFixed(0)}`);
  }
  if (p.role_note) d.push(p.role_note);
  if (adpDelta != null && Math.abs(adpDelta) >= 4)
    d.push(adpDelta > 0 ? `Value: ADP ${p.adp!.toFixed(0)} (+${adpDelta.toFixed(0)})` : `Reach risk vs talent`);
  return d.slice(0, 3);
}

// --- hidden gems (mirror engine/hidden_gems, per position) -----------------
export function computeGems(players: StaticPlayer[], settings: LeagueSettings): any[] {
  const ranked = computeRankings(players, settings);
  const byId = new Map(ranked.map((r) => [r.player_id, r]));
  const byPos: Record<string, { adp: number; proj: number }[]> = {};
  for (const p of players)
    if (p.adp != null)
      (byPos[p.position] ??= []).push({ adp: p.adp, proj: byId.get(p.player_id)?.proj_points ?? 0 });
  const coef: Record<string, [number, number]> = {};
  for (const [pos, pts] of Object.entries(byPos)) {
    if (pts.length < 4) continue;
    // log-linear fit proj ~ a + b*ln(adp+1)
    const xs = pts.map((v) => Math.log(v.adp + 1));
    const ys = pts.map((v) => v.proj);
    const n = xs.length;
    const mx = xs.reduce((a, b) => a + b) / n;
    const my = ys.reduce((a, b) => a + b) / n;
    let num = 0;
    let den = 0;
    for (let i = 0; i < n; i++) {
      num += (xs[i] - mx) * (ys[i] - my);
      den += (xs[i] - mx) ** 2;
    }
    const b = den ? num / den : 0;
    coef[pos] = [my - b * mx, b];
  }
  const gems: any[] = [];
  for (const p of players) {
    const r = byId.get(p.player_id);
    if (!r || p.adp == null) continue;
    const rostered = p.rostered_pct ?? 0.1;
    if (rostered > 0.6) continue;
    const c = coef[p.position];
    const expected = c ? c[0] + c[1] * Math.log(p.adp + 1) : r.proj_points;
    const delta = r.proj_points - expected;
    if (delta < 8) continue;
    gems.push({
      player_id: p.player_id,
      name: p.name,
      position: p.position,
      gem_score: Math.round(delta * (1 - rostered) * 1.05 * 100) / 100,
      projection_vs_adp_delta: Math.round(delta * 10) / 10,
      adp: p.adp,
      rostered_pct: Math.round(rostered * 1000) / 10,
      drivers: [
        `Projected ${delta.toFixed(1)} pts above its ADP tier`,
        `Only ${(rostered * 100).toFixed(0)}% rostered across platforms`,
      ],
    });
  }
  return gems.sort((a, b) => b.gem_score - a.gem_score).slice(0, 25);
}

// --- live draft recommender (mirror engine/draft_engine) -------------------
const ROSTER_TARGETS: Record<string, [number, number]> = {
  QB: [1, 2],
  RB: [2, 5],
  WR: [2, 6],
  TE: [1, 2],
  K: [1, 1],
  DEF: [1, 1],
};

function slotForOverall(overall: number, numTeams: number): number {
  const rnd = Math.floor((overall - 1) / numTeams) + 1;
  const pir = ((overall - 1) % numTeams) + 1;
  return rnd % 2 === 1 ? pir : numTeams - pir + 1;
}

function nextPickForSlot(slot: number, numTeams: number, rounds: number, made: number): number | null {
  for (let rnd = 1; rnd <= rounds; rnd++) {
    const pir = rnd % 2 === 0 ? numTeams - slot + 1 : slot;
    const overall = (rnd - 1) * numTeams + pir;
    if (overall > made) return overall;
  }
  return null;
}

function posValueMult(
  position: string,
  myPositions: string[],
  round: number,
  totalRounds: number,
): [number, string] {
  const counts: Record<string, number> = {};
  for (const p of myPositions) counts[p] = (counts[p] || 0) + 1;
  const have = counts[position] || 0;
  const [starters, target] = ROSTER_TARGETS[position] ?? [1, 2];
  let flexSurplus = 0;
  for (const p of FLEX_ELIGIBLE) flexSurplus += Math.max((counts[p] || 0) - ROSTER_TARGETS[p][0], 0);
  const flexOpen = Math.max(1 - flexSurplus, 0);
  const roundsLeft = totalRounds - round + 1;
  if (position === 'K' || position === 'DEF') {
    if (have >= 1) return [0.05, `${position} already rostered`];
    if (roundsLeft <= 2) return [1.4, `Last-rounds ${position} fill`];
    if (roundsLeft <= 4) return [0.6, `${position} can wait`];
    return [0.08, `Too early for ${position}`];
  }
  if (have < starters) return [(starters - have) >= 2 ? 1.7 : 1.45, `Fills ${position}${have + 1} starter slot`];
  if (FLEX_ELIGIBLE.has(position) && flexOpen > 0 && have < target)
    return [1.15, `Depth for FLEX / bye (${position}${have + 1})`];
  if (have < target) {
    const frac = (target - have) / Math.max(target - starters, 1);
    return [Math.round((0.6 + 0.35 * frac) * 100) / 100, `${position} bench depth`];
  }
  return [0.3, `${position} already deep — value only`];
}

function survival(adp: number | null, myNext: number | null, between: number): number {
  if (adp == null || myNext == null) return 0.5;
  const slack = adp - (myNext - between);
  return Math.round((1 / (1 + Math.exp(-0.45 * (slack - between)))) * 1000) / 1000;
}

export function computeDraftRecommend(
  state: {
    num_teams: number;
    rounds: number;
    my_slot: number;
    picks_made: DraftPickIn[];
    position_filter?: string[] | null;
  },
  ranked: RankingRow[],
): DraftRecommendResponse {
  const byId = new Map(ranked.map((r) => [r.player_id, r]));
  const drafted = new Set(state.picks_made.map((p) => p.player_id));
  let available = ranked.filter((r) => !drafted.has(r.player_id));
  if (state.position_filter?.length)
    available = available.filter((r) => state.position_filter!.includes(r.position));

  const myPositions = state.picks_made
    .filter((p) => p.slot === state.my_slot)
    .map((p) => byId.get(p.player_id)?.position)
    .filter((x): x is string => !!x);

  const made = state.picks_made.length;
  const currentOverall = made + 1;
  const myNext = nextPickForSlot(state.my_slot, state.num_teams, state.rounds, made);
  const picksUntil = myNext ? Math.max(myNext - currentOverall, 0) : 0;
  const round = Math.floor(made / state.num_teams) + 1;

  const needs = rosterNeeds(myPositions);

  const recs = available.map((p) => {
    const [mult, reason] = posValueMult(p.position, myPositions, round, state.rounds);
    const surv = survival(p.adp, myNext, picksUntil);
    const drivers = [p.drivers[0], reason];
    if (p.adp != null && myNext) drivers.push(`ADP ${p.adp.toFixed(0)}; ~${Math.round(surv * 100)}% to survive to #${myNext}`);
    return {
      player_id: p.player_id,
      name: p.name,
      position: p.position,
      team: p.team,
      proj_points: p.proj_points,
      vorp: p.vorp,
      need_weighted_value: Math.round(p.vorp * mult * 100) / 100,
      adp: p.adp,
      reach_risk: reachRisk(p.adp, currentOverall),
      survival_probability: surv,
      drivers: drivers.slice(0, 3),
    };
  });
  recs.sort((a, b) => b.need_weighted_value - a.need_weighted_value);

  const bestByPos: Record<string, any> = {};
  for (const pos of ['QB', 'RB', 'WR', 'TE', 'K', 'DEF'])
    bestByPos[pos] = recs.find((r) => r.position === pos) ?? null;

  return {
    on_the_clock: myNext === currentOverall,
    your_next_overall_pick: myNext ?? 0,
    picks_until_next: picksUntil,
    current_round: round,
    roster_needs: needs,
    scarcity_alerts: scarcityAlerts(available, needs, picksUntil),
    recommendations: recs.slice(0, 8),
    best_available_by_position: bestByPos,
    opponent_styles: opponentStyles(state, byId),
    predicted_picks: [],
    positional_forecast: positionalForecast(state, available, byId, myNext, currentOverall),
  };
}

function rosterNeeds(myPositions: string[]): Record<string, number> {
  const need: Record<string, number> = { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, K: 1, DEF: 1 };
  const counts: Record<string, number> = {};
  for (const p of myPositions) counts[p] = (counts[p] || 0) + 1;
  const out: Record<string, number> = {};
  let flexPool = 0;
  for (const [pos, n] of Object.entries(need)) {
    if (pos === 'FLEX') continue;
    const have = counts[pos] || 0;
    out[pos] = Math.max(n - have, 0);
    if (FLEX_ELIGIBLE.has(pos) && have > n) flexPool += have - n;
  }
  out.FLEX = Math.max((need.FLEX || 0) - flexPool, 0);
  return out;
}

function reachRisk(adp: number | null, overall: number): string {
  if (adp == null) return 'unknown';
  const d = overall - adp;
  if (d <= 6) return 'safe';
  if (d <= 18) return 'slight_reach';
  return 'reach';
}

function scarcityAlerts(available: RankingRow[], needs: Record<string, number>, until: number): string[] {
  const alerts: string[] = [];
  for (const [pos, n] of Object.entries(needs)) {
    if (pos === 'FLEX' || n <= 0) continue;
    const startable = available.filter((p) => p.position === pos && p.vorp > 0);
    const gone = Math.min(startable.length, Math.max(Math.floor(until / 2), 0));
    const left = startable.length - gone;
    if (left > 0 && left <= 3)
      alerts.push(`Only ~${left} startable ${pos}s likely to survive to your next pick`);
  }
  return alerts;
}

function opponentStyles(
  state: { picks_made: DraftPickIn[]; my_slot: number },
  byId: Map<number, RankingRow>,
): any[] {
  const tend: Record<number, Record<string, number>> = {};
  for (const pk of state.picks_made) {
    const pos = byId.get(pk.player_id)?.position;
    if (!pos) continue;
    (tend[pk.slot] ??= {})[pos] = (tend[pk.slot]?.[pos] || 0) + 1;
  }
  const out: any[] = [];
  for (const [slot, counts] of Object.entries(tend)) {
    if (Number(slot) === state.my_slot) continue;
    const rb = counts.RB || 0;
    const wr = counts.WR || 0;
    let style = 'Balanced';
    if (rb >= 2 && wr === 0) style = 'RB-heavy';
    else if (wr >= 2 && rb === 0) style = 'Zero-RB';
    else if ((counts.QB || 0) >= 1 && Object.values(counts).reduce((a, b) => a + b, 0) <= 3) style = 'Early-QB';
    out.push({ slot: Number(slot), style, roster: counts, predicted_next: predictNext(counts) });
  }
  return out;
}

function predictNext(counts: Record<string, number>): string {
  let best = 'RB';
  let score = -1;
  for (const [pos, [starters, total]] of Object.entries(ROSTER_TARGETS)) {
    const have = counts[pos] || 0;
    let need = Math.max(starters - have, 0) * 2 + Math.max(total - have, 0) * 0.3;
    if (pos === 'K' || pos === 'DEF') need = 0.05;
    if (need > score) {
      score = need;
      best = pos;
    }
  }
  return best;
}

function positionalForecast(
  state: { num_teams: number; my_slot: number; picks_made: DraftPickIn[] },
  available: RankingRow[],
  byId: Map<number, RankingRow>,
  myNext: number | null,
  currentOverall: number,
): Record<string, any> {
  const expected: Record<string, number> = {};
  const sim: Record<number, Record<string, number>> = {};
  for (const pk of state.picks_made) {
    const pos = byId.get(pk.player_id)?.position;
    if (pos) (sim[pk.slot] ??= {})[pos] = (sim[pk.slot]?.[pos] || 0) + 1;
  }
  if (myNext) {
    for (let o = currentOverall; o < myNext; o++) {
      const slot = slotForOverall(o, state.num_teams);
      if (slot === state.my_slot) continue;
      const counts = (sim[slot] ??= {});
      const pos = predictNext(counts);
      counts[pos] = (counts[pos] || 0) + 1;
      expected[pos] = (expected[pos] || 0) + 1;
    }
  }
  const out: Record<string, any> = {};
  for (const pos of ['QB', 'RB', 'WR', 'TE']) {
    const startable = available.filter((p) => p.position === pos && p.vorp > 0).length;
    const taken = expected[pos] || 0;
    const remaining = Math.max(startable - taken, 0);
    out[pos] = {
      startable_now: startable,
      expected_taken_before_you: Math.round(taken * 10) / 10,
      likely_remaining: Math.round(remaining * 10) / 10,
      run_risk: remaining <= 2 ? 'high' : remaining <= 4 ? 'medium' : 'low',
    };
  }
  return out;
}
