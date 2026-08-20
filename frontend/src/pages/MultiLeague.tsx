import { useEffect, useState } from 'react';
import { api } from '../api/client';

// Aggregate view across leagues + season simulation snapshot. In production this
// iterates all synced leagues; the scaffold shows the seeded league's sim.
export default function MultiLeague() {
  const [standings, setStandings] = useState<Record<string, unknown>[]>([]);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    try {
      const r = await api.simulateSeason(5000);
      setStandings(r.standings);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Multi-league · season outlook</h1>
        <button className="btn" onClick={run} disabled={busy}>
          {busy ? 'Simulating…' : 'Re-run 5k sims'}
        </button>
      </div>
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-slate-400">
            <tr>
              <th className="p-2">Team</th>
              <th className="p-2 text-right">Exp. wins</th>
              <th className="p-2 text-right">Playoff %</th>
              <th className="p-2 text-right">Champ %</th>
              <th className="p-2 text-right">Avg pts</th>
            </tr>
          </thead>
          <tbody>
            {standings.map((s, i) => (
              <tr key={i} className="border-t border-slate-800">
                <td className="p-2 font-medium">{String(s.team)}</td>
                <td className="p-2 text-right">{String(s.expected_wins)}</td>
                <td className="p-2 text-right">
                  {Math.round(Number(s.playoff_prob) * 100)}%
                </td>
                <td className="text-gridiron-400 p-2 text-right">
                  {Math.round(Number(s.championship_prob) * 100)}%
                </td>
                <td className="p-2 text-right text-slate-400">{String(s.avg_points)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
