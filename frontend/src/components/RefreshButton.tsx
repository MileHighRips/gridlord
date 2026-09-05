import { useState } from 'react';
import { api } from '../api/client';

export default function RefreshButton({
  onRefresh,
}: {
  onRefresh?: () => Promise<void> | void;
}) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function refresh() {
    setBusy(true);
    setMsg('Pulling live data…');
    try {
      const r = await api.refreshLive();
      if (onRefresh) {
        await onRefresh();
      }
      if (r.status === 'cached' || (r.live_players ?? r.players) === 0) {
        const reason = r.reason || 'Live sources returned 0 players.';
        setMsg(`⚠ Live pull returned 0 — ${reason} Showing ${r.players} cached.`);
      } else {
        setMsg(`✓ ${r.players} players + ${r.news} news in ${r.elapsed_seconds}s`);
      }
    } catch (e) {
      setMsg(`✗ Refresh failed — ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center gap-3">
      <button className="btn" onClick={refresh} disabled={busy} aria-busy={busy}>
        {busy ? 'Refreshing…' : '↻ Refresh Live Data'}
      </button>
      {msg && <span className="text-sm text-slate-400">{msg}</span>}
    </div>
  );
}
