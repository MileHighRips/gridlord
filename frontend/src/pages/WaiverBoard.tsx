import { useState } from 'react';
import PositionBadge from '../components/PositionBadge';

const BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';

export default function WaiverBoard() {
  const [faab, setFaab] = useState(100);
  const [needs, setNeeds] = useState<string[]>([]);
  const [rows, setRows] = useState<any[]>([]);

  async function load() {
    const res = await fetch(`${BASE}/api/waivers/recommend`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        faab_budget: 100,
        faab_remaining: faab,
        my_needs: needs,
      }),
    });
    setRows(await res.json());
  }

  function toggleNeed(p: string) {
    setNeeds((n) => (n.includes(p) ? n.filter((x) => x !== p) : [...n, p]));
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Waiver board · FAAB</h1>
      <div className="card flex flex-wrap items-end gap-4">
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          FAAB remaining
          <input
            type="number"
            className="input"
            value={faab}
            onChange={(e) => setFaab(+e.target.value)}
          />
        </label>
        <div className="flex flex-col gap-1 text-xs text-slate-400">
          Needs
          <div className="flex gap-1">
            {['QB', 'RB', 'WR', 'TE'].map((p) => (
              <button
                key={p}
                onClick={() => toggleNeed(p)}
                className={`pill ${needs.includes(p) ? 'bg-gridiron-600 text-white' : 'bg-slate-800 text-slate-300'}`}
              >
                {p}
              </button>
            ))}
          </div>
        </div>
        <button className="btn" onClick={load}>
          Get recommendations
        </button>
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-slate-400">
            <tr>
              <th className="p-2">Player</th>
              <th className="p-2">Pos</th>
              <th className="p-2 text-right">EV</th>
              <th className="p-2 text-right">Rostered</th>
              <th className="p-2 text-right">Suggested FAAB</th>
              <th className="p-2">Priority</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.player_id} className="border-t border-slate-800">
                <td className="p-2 font-medium">{r.name}</td>
                <td className="p-2">
                  <PositionBadge pos={r.position} />
                </td>
                <td className="text-gridiron-400 p-2 text-right">{r.expected_value}</td>
                <td className="p-2 text-right text-slate-400">{r.rostered_pct}%</td>
                <td className="p-2 text-right">
                  ${r.suggested_faab} ({r.suggested_faab_pct}%)
                </td>
                <td className="p-2">
                  <span
                    className={`pill ${r.priority === 'high' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-slate-700/40 text-slate-300'}`}
                  >
                    {r.priority}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
