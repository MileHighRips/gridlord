import { useEffect, useState } from 'react';
import { api, RankingRow, resolveApiBase } from '../api/client';

const BASE = resolveApiBase();

export default function TradeAnalyzer() {
  const [players, setPlayers] = useState<RankingRow[]>([]);
  const [aGives, setAGives] = useState<number[]>([]);
  const [bGives, setBGives] = useState<number[]>([]);
  const [result, setResult] = useState<any>(null);

  useEffect(() => {
    api.rankings().then((r) => setPlayers(r.slice(0, 60)));
  }, []);

  async function analyze() {
    try {
      const res = await fetch(`${BASE}/api/trades/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          team_a: 'You',
          team_b: 'Them',
          team_a_gives: aGives,
          team_b_gives: bGives,
        }),
      });
      if (!res.ok) {
        throw new Error(`${res.status} ${res.statusText}`);
      }
      setResult(await res.json());
    } catch (error) {
      setResult(null);
      window.alert(
        `Trade analysis is unavailable right now. ${error instanceof Error ? error.message : 'Please try again.'}`,
      );
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Trade analyzer</h1>
      <div className="grid gap-4 md:grid-cols-2">
        <SidePicker
          label="You give"
          players={players}
          selected={aGives}
          onChange={setAGives}
        />
        <SidePicker
          label="You get"
          players={players}
          selected={bGives}
          onChange={setBGives}
        />
      </div>
      <button
        className="btn"
        onClick={analyze}
        disabled={!aGives.length || !bGives.length}
      >
        Analyze trade
      </button>

      {result && (
        <div className="card">
          <p className="text-lg">
            Verdict: <b className="text-gridiron-400">{result.verdict}</b> ·{' '}
            {result.fairness}
          </p>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {['side_a', 'side_b'].map((k) => (
              <div key={k} className="rounded-lg bg-slate-800/50 p-3 text-sm">
                <h3 className="font-bold">{result[k].team}</h3>
                <p>Net VORP: {result[k].net_vorp}</p>
                <p>ROS pts Δ: {result[k].ros_points_delta}</p>
                <p>Risk: {result[k].risk_score}</p>
              </div>
            ))}
          </div>
          {result.counteroffers?.length > 0 && (
            <ul className="mt-3 list-disc pl-5 text-sm text-slate-400">
              {result.counteroffers.map((c: string) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function SidePicker({
  label,
  players,
  selected,
  onChange,
}: {
  label: string;
  players: RankingRow[];
  selected: number[];
  onChange: (v: number[]) => void;
}) {
  function toggle(id: number) {
    onChange(
      selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id],
    );
  }
  return (
    <div className="card">
      <h2 className="mb-2 font-bold">{label}</h2>
      <div className="max-h-72 space-y-1 overflow-auto">
        {players.map((p) => (
          <label
            key={p.player_id}
            className="flex cursor-pointer items-center gap-2 rounded p-1 hover:bg-slate-800"
          >
            <input
              type="checkbox"
              checked={selected.includes(p.player_id)}
              onChange={() => toggle(p.player_id)}
            />
            <span className="flex-1">{p.name}</span>
            <span className="text-slate-400">{p.vorp.toFixed(1)}</span>
          </label>
        ))}
      </div>
    </div>
  );
}
