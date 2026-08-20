import { useEffect, useState } from 'react';
import { api, SourceRow } from '../api/client';

// Transparency board: which ranking + news providers are live right now, and
// which light up once you add an API key or subscription.
export default function Sources() {
  const [rows, setRows] = useState<SourceRow[]>([]);
  const [counts, setCounts] = useState({ live: 0, pending: 0 });

  useEffect(() => {
    api.sources().then((d) => {
      setRows(d.sources);
      setCounts({ live: d.live_count, pending: d.pending_count });
    });
  }, []);

  const rankings = rows.filter((r) => r.kind === 'rankings');
  const news = rows.filter((r) => r.kind === 'news');

  return (
    <div className="space-y-5">
      <div>
        <div className="eyebrow">Transparency</div>
        <h1 className="font-display text-2xl font-bold tracking-wide">Data Sources</h1>
        <p className="text-muted text-sm">
          <span className="text-good">{counts.live} live</span> ·{' '}
          <span className="text-gold-300">{counts.pending} pending credentials</span>. Add
          a key or subscription and the provider blends into rankings automatically.
        </p>
      </div>

      <SourceGroup title="Rankings & Projections" rows={rankings} />
      <SourceGroup title="News & Insight" rows={news} />
    </div>
  );
}

function SourceGroup({ title, rows }: { title: string; rows: SourceRow[] }) {
  return (
    <section>
      <div className="eyebrow mb-2">{title}</div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {rows.map((r) => (
          <div
            key={r.key + r.kind}
            className="card flex items-start justify-between gap-3"
          >
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold">{r.name}</span>
                {r.weight !== 1 && (
                  <span className="pill bg-ink-700 text-muted">×{r.weight}</span>
                )}
              </div>
              <p className="text-muted mt-1 text-xs">{r.note}</p>
            </div>
            <span
              className={`pill shrink-0 ${
                r.available ? 'bg-good/20 text-good' : 'bg-gold-400/15 text-gold-300'
              }`}
            >
              {r.available ? '● Live' : '○ Add key'}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
