import { useEffect, useState } from 'react';
import { api } from '../api/client';
import PositionBadge from '../components/PositionBadge';
import RefreshButton from '../components/RefreshButton';

interface Gem {
  player_id: number;
  name: string;
  position: string;
  gem_score: number;
  projection_vs_adp_delta: number;
  adp: number | null;
  rostered_pct: number;
  drivers: string[];
}

// Hidden gems: players whose projection outruns their draft cost (ADP tier),
// lightly rostered and/or trending up.
export default function HiddenGems() {
  const [gems, setGems] = useState<Gem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .hiddenGems()
      .then((g) => setGems(g as unknown as Gem[]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">💎 Hidden Gems</h1>
          <p className="text-sm text-slate-400">
            Projection vs. ADP-tier delta × usage trend × (1 − rostered %).
          </p>
        </div>
        <RefreshButton />
      </div>

      {loading && <p className="text-slate-500">Loading…</p>}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {gems.map((g) => (
          <div key={g.player_id} className="card">
            <div className="mb-2 flex items-center justify-between">
              <span className="font-semibold">{g.name}</span>
              <PositionBadge pos={g.position} />
            </div>
            <div className="flex flex-wrap gap-x-3 text-xs text-slate-400">
              <span className="text-emerald-400">score {g.gem_score}</span>
              <span>+{g.projection_vs_adp_delta} vs ADP tier</span>
              <span>ADP {g.adp?.toFixed(0) ?? '—'}</span>
              <span>{g.rostered_pct}% rostered</span>
            </div>
            <ul className="mt-2 list-disc pl-4 text-xs text-slate-500">
              {g.drivers.map((d) => (
                <li key={d}>{d}</li>
              ))}
            </ul>
          </div>
        ))}
        {!loading && gems.length === 0 && (
          <p className="text-slate-500">
            No gems flagged yet — run a live refresh to pull projections + ADP.
          </p>
        )}
      </div>
    </div>
  );
}
