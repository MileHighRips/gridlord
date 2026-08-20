import { useEffect, useState } from 'react';
import { api, RankingRow } from '../api/client';
import PositionBadge from '../components/PositionBadge';
import RefreshButton from '../components/RefreshButton';

export default function Rankings() {
  const [rows, setRows] = useState<RankingRow[]>([]);
  const [pos, setPos] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .rankings(pos || undefined)
      .then(setRows)
      .finally(() => setLoading(false));
  }, [pos]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="eyebrow">Consensus board</div>
          <h1 className="font-display text-2xl font-bold tracking-wide">Rankings</h1>
          <p className="text-muted text-sm">
            Sleeper projections + FantasyPros expert consensus, league-size VORP, with
            boom/bust and ADP divergence.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            className="input"
            value={pos}
            onChange={(e) => setPos(e.target.value)}
            aria-label="Position filter"
          >
            <option value="">All positions</option>
            {['QB', 'RB', 'WR', 'TE', 'K', 'DEF'].map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
          <RefreshButton />
        </div>
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-ink-500 text-muted border-b text-left">
            <tr className="eyebrow">
              <th className="p-2">#</th>
              <th className="p-2">Player</th>
              <th className="p-2">Pos</th>
              <th className="p-2">Tier</th>
              <th className="p-2 text-right">Proj</th>
              <th className="p-2 text-right">VORP</th>
              <th className="p-2 text-right">ECR</th>
              <th className="p-2 text-right">Boom</th>
              <th className="p-2 text-right">Bust</th>
              <th className="p-2 text-right">Div</th>
              <th className="p-2">Why</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={11} className="text-muted p-4 text-center">
                  Loading…
                </td>
              </tr>
            )}
            {rows.map((r) => (
              <tr
                key={r.player_id}
                className="border-ink-600/60 hover:bg-ink-800/50 border-t align-top"
              >
                <td className="stat text-muted p-2">{r.rank}</td>
                <td className="p-2 font-medium">
                  {r.name} <span className="text-muted text-xs">{r.team}</span>
                </td>
                <td className="p-2">
                  <PositionBadge pos={r.position} />
                </td>
                <td className="stat text-muted p-2">T{r.tier}</td>
                <td className="stat p-2 text-right">{r.proj_points.toFixed(1)}</td>
                <td className="stat text-gold-300 p-2 text-right">{r.vorp.toFixed(1)}</td>
                <td className="stat text-muted p-2 text-right">
                  {r.ecr != null ? r.ecr.toFixed(0) : '—'}
                  {r.ecr_delta != null && Math.abs(r.ecr_delta) >= 2 && (
                    <span className={r.ecr_delta > 0 ? 'text-good' : 'text-danger'}>
                      {r.ecr_delta > 0 ? ' ▲' : ' ▼'}
                    </span>
                  )}
                </td>
                <td className="stat text-good p-2 text-right">
                  {r.boom_pct != null ? `${r.boom_pct.toFixed(0)}%` : '—'}
                </td>
                <td className="stat text-danger p-2 text-right">
                  {r.bust_pct != null ? `${r.bust_pct.toFixed(0)}%` : '—'}
                </td>
                <td
                  className={`stat p-2 text-right ${
                    (r.adp_divergence ?? 0) > 0 ? 'text-good' : 'text-danger'
                  }`}
                >
                  {r.adp_divergence != null ? r.adp_divergence.toFixed(0) : '—'}
                </td>
                <td className="text-muted p-2 text-xs">
                  <ul className="list-disc pl-4">
                    {r.drivers.map((d) => (
                      <li key={d}>{d}</li>
                    ))}
                  </ul>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
