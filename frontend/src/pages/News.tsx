import { useEffect, useState } from 'react';
import { api, InjuryRow, NewsRow } from '../api/client';
import PositionBadge from '../components/PositionBadge';

// Aggregated player news + live injury report. Injuries here discount rankings.
export default function News() {
  const [news, setNews] = useState<NewsRow[]>([]);
  const [injuries, setInjuries] = useState<InjuryRow[]>([]);
  const [tag, setTag] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([api.news(tag || undefined), api.injuries()])
      .then(([n, i]) => {
        setNews(n);
        setInjuries(i);
      })
      .finally(() => setLoading(false));
  }, [tag]);

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold">Player News</h1>
          <select
            className="input"
            value={tag}
            onChange={(e) => setTag(e.target.value)}
            aria-label="Filter news"
          >
            <option value="">All</option>
            <option value="injury">Injuries</option>
            <option value="role_change">Role changes</option>
          </select>
        </div>
        {loading && <p className="text-slate-500">Loading…</p>}
        {!loading && news.length === 0 && (
          <p className="text-slate-500">
            No news cached yet. Hit “Refresh Data” on the Dashboard to pull the latest.
          </p>
        )}
        <ul className="space-y-2">
          {news.map((n) => (
            <li key={n.id} className="card">
              <div className="mb-1 flex flex-wrap items-center gap-2">
                {n.tags.map((t) => (
                  <span
                    key={t}
                    className={`pill ${
                      t === 'injury'
                        ? 'bg-rose-500/20 text-rose-300'
                        : t === 'role_change'
                          ? 'bg-amber-500/20 text-amber-300'
                          : 'bg-slate-600/30 text-slate-300'
                    }`}
                  >
                    {t}
                  </span>
                ))}
                <span className="text-xs text-slate-500">{n.source}</span>
                {n.player_name && (
                  <span className="text-gridiron-400 text-xs">· {n.player_name}</span>
                )}
              </div>
              <a
                href={n.url ?? '#'}
                target="_blank"
                rel="noreferrer"
                className="hover:text-gridiron-400 font-medium"
              >
                {n.headline}
              </a>
              {n.summary && (
                <p className="mt-1 line-clamp-2 text-sm text-slate-400">{n.summary}</p>
              )}
            </li>
          ))}
        </ul>
      </section>

      <aside className="card h-fit">
        <h2 className="mb-3 font-bold">🩺 Injury report</h2>
        <p className="mb-3 text-xs text-slate-500">
          Active designations discount each player's projection & ranking.
        </p>
        <ul className="space-y-2">
          {injuries.slice(0, 40).map((i) => (
            <li
              key={i.player_id}
              className="flex items-center justify-between border-b border-slate-800 py-1 text-sm"
            >
              <span className="flex items-center gap-2">
                <PositionBadge pos={i.position} />
                {i.name}
              </span>
              <span
                className={`pill ${
                  ['Out', 'IR', 'PUP', 'Suspended'].includes(i.injury_status)
                    ? 'bg-rose-500/20 text-rose-300'
                    : 'bg-amber-500/20 text-amber-300'
                }`}
              >
                {i.injury_status}
              </span>
            </li>
          ))}
          {injuries.length === 0 && (
            <li className="text-sm text-slate-500">No active injuries in the dataset.</li>
          )}
        </ul>
      </aside>
    </div>
  );
}
