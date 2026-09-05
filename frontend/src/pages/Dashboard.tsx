import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, RankingRow } from '../api/client';
import PositionBadge from '../components/PositionBadge';
import RefreshButton from '../components/RefreshButton';

export default function Dashboard() {
  const [top, setTop] = useState<RankingRow[]>([]);
  const [gems, setGems] = useState<Record<string, unknown>[]>([]);
  const [online, setOnline] = useState<boolean | null>(null);

  const loadDashboard = async () => {
    const [rankings, hidden] = await Promise.all([api.rankings(), api.hiddenGems()]);
    setTop(rankings.slice(0, 10));
    setGems(hidden.slice(0, 6));
  };

  useEffect(() => {
    const boot = async () => {
      // Show the board immediately from the live API or cached snapshot so the
      // dashboard is never blank while a slow live refresh runs.
      await loadDashboard();

      try {
        await api.health();
        setOnline(true);
      } catch {
        setOnline(false);
      }

      // Throttle the automatic background refresh so simply opening the app does
      // not fire a heavy ~30s ingest every time (which also causes DB-lock
      // collisions). Auto-refresh at most once every 15 minutes; the Refresh
      // button always forces a fresh pull on demand.
      const REFRESH_TS_KEY = 'gridlord_last_auto_refresh';
      const FIFTEEN_MIN = 15 * 60 * 1000;
      const last = Number(window.localStorage.getItem(REFRESH_TS_KEY) || 0);
      if (Date.now() - last < FIFTEEN_MIN) return;

      api
        .refreshLive()
        .then(() => {
          window.localStorage.setItem(REFRESH_TS_KEY, String(Date.now()));
          return loadDashboard();
        })
        .catch(() => {
          // Keep the already-rendered cached board if the refresh fails.
        });
    };

    void boot();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-black">The League · 2026</h1>
          <p className="text-sm text-slate-400">
            14-team H2H PPR w/ bonus yardage · backend{' '}
            <span className={online ? 'text-emerald-400' : 'text-rose-400'}>
              {online == null ? '…' : online ? 'online' : 'offline'}
            </span>
          </p>
        </div>
        <RefreshButton onRefresh={loadDashboard} />
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <QuickCard to="/draft" title="Live Draft" desc="Real-time pick recommendations" />
        <QuickCard to="/rankings" title="Rankings" desc="VORP + explainability" />
        <QuickCard to="/lineup" title="Lineup" desc="Weekly optimizer" />
        <QuickCard to="/trades" title="Trades" desc="EV + season impact" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card">
          <h2 className="mb-3 font-bold">Top 10 overall</h2>
          <ol className="space-y-1 text-sm">
            {top.map((r) => (
              <li
                key={r.player_id}
                className="flex items-center justify-between border-b border-slate-800 py-1"
              >
                <span>
                  <span className="mr-2 text-slate-500">{r.rank}</span>
                  {r.name}
                </span>
                <span className="flex items-center gap-2">
                  <PositionBadge pos={r.position} />
                  <span className="text-gridiron-400">{r.vorp.toFixed(1)}</span>
                </span>
              </li>
            ))}
          </ol>
        </div>

        <div className="card">
          <h2 className="mb-3 font-bold">💎 Hidden gems</h2>
          <ul className="space-y-2 text-sm">
            {gems.map((g) => (
              <li key={String(g.player_id)} className="border-b border-slate-800 py-1">
                <div className="flex items-center justify-between">
                  <span>{String(g.name)}</span>
                  <span className="text-emerald-400">
                    +{String(g.projection_vs_adp_delta)} vs ADP
                  </span>
                </div>
                <p className="text-xs text-slate-500">{(g.drivers as string[])?.[0]}</p>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

function QuickCard({ to, title, desc }: { to: string; title: string; desc: string }) {
  return (
    <Link to={to} className="card hover:border-gridiron-600 transition">
      <h3 className="font-bold">{title}</h3>
      <p className="text-sm text-slate-400">{desc}</p>
    </Link>
  );
}
