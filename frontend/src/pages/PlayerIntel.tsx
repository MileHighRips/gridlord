import { useEffect, useState } from 'react';
import { api, IntelRow } from '../api/client';
import PositionBadge from '../components/PositionBadge';
import RefreshButton from '../components/RefreshButton';

const SORTS = [
  { key: 'usage', label: 'Analyst Buzz' },
  { key: 'risers', label: 'ECR Risers' },
  { key: 'boom', label: 'Boom %' },
  { key: 'bust', label: 'Bust %' },
];

// Advanced player intelligence: usage/buzz velocity, role changes, boom/bust,
// expert-consensus movement, injury & practice signals — all in one board.
export default function PlayerIntel() {
  const [sort, setSort] = useState('usage');
  const [rows, setRows] = useState<IntelRow[]>([]);
  const [loading, setLoading] = useState(true);

  const loadIntel = async () => {
    setLoading(true);
    try {
      const rows = await api.playerIntel(sort);
      setRows(rows);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadIntel();
  }, [sort]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="eyebrow">Advanced Intelligence</div>
          <h1 className="font-display text-2xl font-bold tracking-wide">Player Intel</h1>
          <p className="text-muted text-sm">
            Usage trend, role shifts, boom/bust and expert movement — the signals that
            move before the points do.
          </p>
        </div>
        <RefreshButton onRefresh={loadIntel} />
      </div>

      <div className="flex flex-wrap gap-1.5">
        {SORTS.map((s) => (
          <button
            key={s.key}
            onClick={() => setSort(s.key)}
            className={`pill px-3 py-1 ${
              sort === s.key
                ? 'bg-gold-400 text-ink-950'
                : 'bg-ink-700 text-muted hover:text-chalk'
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {loading && <p className="text-muted">Reading the tape…</p>}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {rows.map((r) => (
          <article key={r.player_id} className="card">
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <PositionBadge pos={r.position} />
                <span className="font-semibold">{r.name}</span>
                <span className="text-muted text-xs">{r.team}</span>
              </div>
              {r.ecr_delta != null && Math.abs(r.ecr_delta) >= 1 && (
                <span
                  className={`stat text-xs ${r.ecr_delta > 0 ? 'text-good' : 'text-danger'}`}
                >
                  {r.ecr_delta > 0 ? '▲' : '▼'} {Math.abs(r.ecr_delta).toFixed(0)} ECR
                </span>
              )}
            </div>

            {r.role_note && <p className="text-gold-300 mb-2 text-sm">{r.role_note}</p>}

            <div className="grid grid-cols-3 gap-2 text-center">
              <Meter label="Usage" value={r.usage_score} suffix="" tone="volt" />
              <Meter label="Boom" value={r.boom_pct} suffix="%" tone="good" />
              <Meter label="Bust" value={r.bust_pct} suffix="%" tone="danger" />
            </div>

            <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
              {r.ecr != null && (
                <span className="pill bg-ink-700 text-muted">ECR {r.ecr.toFixed(0)}</span>
              )}
              {r.practice_status && (
                <span className="pill bg-volt-500/20 text-volt-400">
                  Practice: {r.practice_status}
                </span>
              )}
              {r.injury_status && (
                <span className="pill bg-danger/20 text-danger">{r.injury_status}</span>
              )}
              {r.volatility_index != null && (
                <span className="pill bg-ink-700 text-muted">
                  Volatility {r.volatility_index.toFixed(0)}
                </span>
              )}
            </div>
          </article>
        ))}
      </div>
      {!loading && rows.length === 0 && (
        <p className="text-muted">Run a live refresh to populate intelligence signals.</p>
      )}
    </div>
  );
}

function Meter({
  label,
  value,
  suffix,
  tone,
}: {
  label: string;
  value: number | null;
  suffix: string;
  tone: 'volt' | 'good' | 'danger';
}) {
  const pct = Math.max(0, Math.min(100, value ?? 0));
  const bar =
    tone === 'good' ? 'bg-good' : tone === 'danger' ? 'bg-danger' : 'bg-volt-400';
  return (
    <div>
      <div className="eyebrow mb-1">{label}</div>
      <div className="stat text-chalk text-sm">
        {value != null ? `${value.toFixed(0)}${suffix}` : '—'}
      </div>
      <div className="bg-ink-700 mt-1 h-1.5 overflow-hidden rounded-full">
        <div className={`h-full ${bar}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
