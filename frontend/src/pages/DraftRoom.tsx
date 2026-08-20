import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { api, DraftPickIn, DraftRecommendResponse, RankingRow } from '../api/client';
import PositionBadge from '../components/PositionBadge';

// Live draft assistant: manually record picks as they happen; get a real-time
// recommendation for your slot with roster-need weighting + survival odds.
export default function DraftRoom() {
  const [board, setBoard] = useState<RankingRow[]>([]);
  const [numTeams, setNumTeams] = useState(14);
  const [rounds, setRounds] = useState(16);
  const [mySlot, setMySlot] = useState(7);
  const [picks, setPicks] = useState<DraftPickIn[]>([]);
  const [rec, setRec] = useState<DraftRecommendResponse | null>(null);
  const [search, setSearch] = useState('');
  const [posFilter, setPosFilter] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .rankings()
      .then(setBoard)
      .catch((e) => setError((e as Error).message));
  }, []);

  const draftedIds = useMemo(() => new Set(picks.map((p) => p.player_id)), [picks]);
  const nextOverall = picks.length + 1;
  const slotOnClock = slotForOverall(nextOverall, numTeams);

  const available = useMemo(
    () =>
      board
        .filter((p) => !draftedIds.has(p.player_id))
        .filter((p) => (posFilter ? p.position === posFilter : true))
        .filter((p) =>
          search ? p.name.toLowerCase().includes(search.toLowerCase()) : true,
        ),
    [board, draftedIds, posFilter, search],
  );

  async function refreshRec(nextPicks = picks) {
    try {
      const r = await api.draftRecommend({
        league_id: 1,
        num_teams: numTeams,
        rounds,
        my_slot: mySlot,
        draft_type: 'snake',
        picks_made: nextPicks,
        position_filter: posFilter ? [posFilter] : null,
      });
      setRec(r);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    if (board.length) refreshRec();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [board.length, numTeams, rounds, mySlot, posFilter]);

  function recordPick(player: RankingRow) {
    const next = [
      ...picks,
      { overall_pick: nextOverall, player_id: player.player_id, slot: slotOnClock },
    ];
    setPicks(next);
    refreshRec(next);
  }

  function undo() {
    const next = picks.slice(0, -1);
    setPicks(next);
    refreshRec(next);
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
      {/* Left: controls + available board */}
      <section className="space-y-4">
        <div className="card flex flex-wrap items-end gap-4">
          <Field label="Teams">
            <input
              type="number"
              className="input"
              value={numTeams}
              min={2}
              max={20}
              onChange={(e) => setNumTeams(+e.target.value)}
            />
          </Field>
          <Field label="Rounds">
            <input
              type="number"
              className="input"
              value={rounds}
              min={1}
              max={30}
              onChange={(e) => setRounds(+e.target.value)}
            />
          </Field>
          <Field label="My slot">
            <input
              type="number"
              className="input"
              value={mySlot}
              min={1}
              max={numTeams}
              onChange={(e) => setMySlot(+e.target.value)}
            />
          </Field>
          <button className="btn-ghost" onClick={undo} disabled={!picks.length}>
            ↩ Undo pick
          </button>
          <div className="w-full text-sm text-slate-400 lg:ml-auto lg:w-auto">
            Pick <b className="text-slate-100">{nextOverall}</b> · Round{' '}
            {Math.floor((nextOverall - 1) / numTeams) + 1} · Slot{' '}
            <b className={slotOnClock === mySlot ? 'text-gridiron-400' : ''}>
              {slotOnClock}
            </b>{' '}
            on the clock
          </div>
        </div>

        <div className="card">
          <div className="mb-3 flex gap-2">
            <input
              className="input flex-1"
              placeholder="Search player…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search player"
            />
            <select
              className="input"
              value={posFilter}
              onChange={(e) => setPosFilter(e.target.value)}
              aria-label="Filter position"
            >
              <option value="">All</option>
              {['QB', 'RB', 'WR', 'TE', 'K', 'DEF'].map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </div>
          {error && <p className="mb-2 text-sm text-rose-400">{error}</p>}
          <div className="max-h-[60vh] overflow-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-slate-900 text-left text-slate-400">
                <tr>
                  <th className="p-2">#</th>
                  <th className="p-2">Player</th>
                  <th className="p-2">Pos</th>
                  <th className="hidden p-2 text-right sm:table-cell">Proj</th>
                  <th className="hidden p-2 text-right sm:table-cell">VORP</th>
                  <th className="hidden p-2 text-right sm:table-cell">ADP</th>
                  <th className="p-2"></th>
                </tr>
              </thead>
              <tbody>
                {available.slice(0, 120).map((p) => (
                  <tr key={p.player_id} className="border-t border-slate-800">
                    <td className="p-2 text-slate-500">{p.rank}</td>
                    <td className="p-2 font-medium">
                      {p.name} <span className="text-xs text-slate-500">{p.team}</span>
                    </td>
                    <td className="p-2">
                      <PositionBadge pos={p.position} />
                    </td>
                    <td className="hidden p-2 text-right sm:table-cell">
                      {p.proj_points.toFixed(1)}
                    </td>
                    <td className="text-gridiron-400 hidden p-2 text-right sm:table-cell">
                      {p.vorp.toFixed(1)}
                    </td>
                    <td className="hidden p-2 text-right text-slate-400 sm:table-cell">
                      {p.adp?.toFixed(0) ?? '—'}
                    </td>
                    <td className="p-2 text-right">
                      <button className="btn" onClick={() => recordPick(p)}>
                        Draft
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Right: live recommendation panel */}
      <aside className="space-y-4">
        <div className={`card ${rec?.on_the_clock ? 'ring-gridiron-500 ring-2' : ''}`}>
          <h2 className="mb-1 text-lg font-bold">
            {rec?.on_the_clock ? "🎯 You're on the clock" : 'Live Recommendation'}
          </h2>
          {rec && (
            <p className="mb-3 text-sm text-slate-400">
              Your next pick:{' '}
              <b className="text-slate-100">#{rec.your_next_overall_pick}</b> ·{' '}
              {rec.picks_until_next} picks away
            </p>
          )}
          {rec?.scarcity_alerts.map((a) => (
            <p
              key={a}
              className="mb-2 rounded bg-amber-500/10 p-2 text-xs text-amber-300"
            >
              ⚠ {a}
            </p>
          ))}
          <ol className="space-y-2">
            {rec?.recommendations.slice(0, 6).map((r, i) => (
              <li key={r.player_id} className="rounded-lg border border-slate-800 p-3">
                <div className="flex items-center justify-between">
                  <span className="font-semibold">
                    {i + 1}. {r.name}
                  </span>
                  <PositionBadge pos={r.position} />
                </div>
                <div className="mt-1 flex flex-wrap gap-x-3 text-xs text-slate-400">
                  <span>Value {r.need_weighted_value.toFixed(1)}</span>
                  <span>VORP {r.vorp.toFixed(1)}</span>
                  <span>ADP {r.adp?.toFixed(0) ?? '—'}</span>
                  <span
                    className={
                      r.reach_risk === 'reach'
                        ? 'text-rose-400'
                        : r.reach_risk === 'slight_reach'
                          ? 'text-amber-400'
                          : 'text-emerald-400'
                    }
                  >
                    {r.reach_risk.replace('_', ' ')}
                  </span>
                  <span>{Math.round(r.survival_probability * 100)}% survives</span>
                </div>
                <ul className="mt-1 list-disc pl-4 text-xs text-slate-500">
                  {r.drivers.map((d) => (
                    <li key={d}>{d}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        </div>

        <div className="card">
          <h3 className="mb-2 font-semibold">Roster needs</h3>
          <div className="flex flex-wrap gap-2">
            {rec &&
              Object.entries(rec.roster_needs).map(([pos, n]) => (
                <span
                  key={pos}
                  className={`pill ${n > 0 ? 'bg-gridiron-600/30 text-gridiron-300' : 'bg-slate-700/40 text-slate-400'}`}
                >
                  {pos}: {n}
                </span>
              ))}
          </div>
        </div>

        {rec && Object.keys(rec.positional_forecast).length > 0 && (
          <div className="card">
            <h3 className="mb-2 font-semibold">Positional run forecast</h3>
            <p className="text-muted mb-2 text-xs">
              Startable players likely to survive to your next pick.
            </p>
            <div className="space-y-1.5">
              {Object.entries(rec.positional_forecast).map(([pos, f]) => (
                <div key={pos} className="flex items-center gap-2 text-sm">
                  <span className="text-muted w-8">{pos}</span>
                  <div className="bg-ink-700 h-2 flex-1 overflow-hidden rounded-full">
                    <div
                      className={`h-full ${
                        f.run_risk === 'high'
                          ? 'bg-danger'
                          : f.run_risk === 'medium'
                            ? 'bg-gold-400'
                            : 'bg-good'
                      }`}
                      style={{
                        width: `${Math.min(100, (f.likely_remaining / Math.max(f.startable_now, 1)) * 100)}%`,
                      }}
                    />
                  </div>
                  <span className="stat text-muted w-10 text-right text-xs">
                    ~{f.likely_remaining}
                  </span>
                  {f.run_risk === 'high' && (
                    <span className="pill bg-danger/20 text-danger">RUN</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {rec && rec.opponent_styles.length > 0 && (
          <div className="card">
            <h3 className="mb-2 font-semibold">Opponent tendencies</h3>
            <div className="max-h-48 space-y-1 overflow-auto text-sm">
              {rec.opponent_styles.map((o) => (
                <div
                  key={o.slot}
                  className="border-ink-600/50 flex items-center justify-between border-b py-1"
                >
                  <span className="text-muted">Slot {o.slot}</span>
                  <span className="pill bg-ink-700 text-chalk">{o.style}</span>
                  <span className="text-muted text-xs">
                    next: <b className="text-gold-300">{o.predicted_next}</b>
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}

function slotForOverall(overall: number, numTeams: number): number {
  const rnd = Math.floor((overall - 1) / numTeams) + 1;
  const posInRound = ((overall - 1) % numTeams) + 1;
  return rnd % 2 === 1 ? posInRound : numTeams - posInRound + 1;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs text-slate-400">
      {label}
      {children}
    </label>
  );
}
