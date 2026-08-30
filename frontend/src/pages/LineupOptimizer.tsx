import { useEffect, useState } from 'react';
import { api, RankingRow, resolveApiBase } from '../api/client';
import PositionBadge from '../components/PositionBadge';

const BASE = resolveApiBase();
const SLOTS = ['QB', 'RB', 'RB', 'WR', 'WR', 'TE', 'FLEX', 'K', 'DEF'];

export default function LineupOptimizer() {
  const [pool, setPool] = useState<RankingRow[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [result, setResult] = useState<any>(null);

  useEffect(() => {
    api.rankings().then((r) => setPool(r.slice(0, 40)));
  }, []);

  function toggle(id: number) {
    const next = new Set(selected);
    next.has(id) ? next.delete(id) : next.add(id);
    setSelected(next);
  }

  async function optimize() {
    try {
      const res = await fetch(`${BASE}/api/lineup/optimize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ player_ids: [...selected], slots: SLOTS }),
      });
      if (!res.ok) {
        throw new Error(`${res.status} ${res.statusText}`);
      }
      setResult(await res.json());
    } catch (error) {
      setResult(null);
      window.alert(
        `Live lineup optimization is unavailable right now. ${error instanceof Error ? error.message : 'Please try again.'}`,
      );
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="card">
        <h1 className="mb-3 text-xl font-bold">Pick your roster pool</h1>
        <p className="mb-3 text-sm text-slate-400">
          Select players; the optimizer fills {SLOTS.join(', ')} for max projected points.
        </p>
        <div className="max-h-[60vh] space-y-1 overflow-auto">
          {pool.map((p) => (
            <label
              key={p.player_id}
              className="flex cursor-pointer items-center gap-2 rounded p-1 hover:bg-slate-800"
            >
              <input
                type="checkbox"
                checked={selected.has(p.player_id)}
                onChange={() => toggle(p.player_id)}
              />
              <PositionBadge pos={p.position} />
              <span className="flex-1">{p.name}</span>
              <span className="text-slate-400">{p.proj_points.toFixed(1)}</span>
            </label>
          ))}
        </div>
        <button className="btn mt-3" onClick={optimize} disabled={!selected.size}>
          Optimize lineup
        </button>
      </section>

      <section className="card">
        <h2 className="mb-3 text-xl font-bold">Optimal lineup</h2>
        {result ? (
          <>
            <p className="mb-3 text-sm">
              Projected total:{' '}
              <b className="text-gridiron-400">{result.projected_total}</b> pts/wk
            </p>
            <table className="w-full text-sm">
              <tbody>
                {result.starters?.map((s: any, i: number) => (
                  <tr key={i} className="border-t border-slate-800">
                    <td className="p-2 text-slate-400">{s.slot}</td>
                    <td className="p-2 font-medium">{s.name}</td>
                    <td className="p-2 text-right">{s.proj_points}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : (
          <p className="text-sm text-slate-500">Select players and click optimize.</p>
        )}
      </section>
    </div>
  );
}
