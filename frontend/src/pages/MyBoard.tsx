import { useEffect, useState } from 'react';
import { api, BoardPlayer, RankingRow } from '../api/client';
import PositionBadge from '../components/PositionBadge';

// Build your own draft board: start from consensus, then reorder to your taste.
// Saved per account (or locally as a guest) and usable during the live draft.
export default function MyBoard() {
  const [board, setBoard] = useState<BoardPlayer[]>([]);
  const [search, setSearch] = useState('');
  const [results, setResults] = useState<RankingRow[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getBoard()
      .then((d) => setBoard(d.players))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (search.length < 2) {
      setResults([]);
      return;
    }
    const ids = new Set(board.map((b) => b.player_id));
    api.rankings().then((rows) =>
      setResults(
        rows
          .filter((r) => r.name.toLowerCase().includes(search.toLowerCase()))
          .filter((r) => !ids.has(r.player_id))
          .slice(0, 8),
      ),
    );
  }, [search, board]);

  function move(i: number, dir: -1 | 1) {
    const j = i + dir;
    if (j < 0 || j >= board.length) return;
    const next = [...board];
    [next[i], next[j]] = [next[j], next[i]];
    setBoard(next);
  }
  function toTop(i: number) {
    const next = [...board];
    const [item] = next.splice(i, 1);
    next.unshift(item);
    setBoard(next);
  }
  function remove(i: number) {
    setBoard(board.filter((_, idx) => idx !== i));
  }
  function add(r: RankingRow) {
    setBoard([
      ...board,
      { player_id: r.player_id, name: r.name, position: r.position, team: r.team },
    ]);
    setSearch('');
    setResults([]);
  }

  async function save() {
    setStatus('Saving…');
    try {
      await api.saveBoard(board.map((b) => b.player_id));
      setStatus('✓ Board saved — the Live Draft can use it');
    } catch (e) {
      setStatus((e as Error).message);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="eyebrow">Your rankings</div>
          <h1 className="font-display text-2xl font-bold tracking-wide">
            My Draft Board
          </h1>
          <p className="text-muted text-sm">
            Seeded from consensus. Reorder to your conviction — it saves to your account.
          </p>
        </div>
        <button className="btn" onClick={save}>
          Save board
        </button>
      </div>
      {status && <p className="text-gold-300 text-sm">{status}</p>}

      <div className="card">
        <div className="relative mb-3">
          <input
            className="input w-full"
            placeholder="Add a player…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {results.length > 0 && (
            <div className="border-ink-500 bg-ink-800 absolute z-10 mt-1 w-full overflow-hidden rounded-lg border shadow-xl">
              {results.map((r) => (
                <button
                  key={r.player_id}
                  onClick={() => add(r)}
                  className="hover:bg-ink-700 flex w-full items-center gap-2 px-3 py-2 text-left text-sm"
                >
                  <PositionBadge pos={r.position} />
                  {r.name}
                  <span className="text-muted ml-auto text-xs">{r.team}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {loading ? (
          <p className="text-muted">Loading your board…</p>
        ) : (
          <ol className="divide-ink-600/50 divide-y">
            {board.map((b, i) => (
              <li key={b.player_id} className="flex items-center gap-2 py-1.5">
                <span className="stat text-muted w-8 text-right">{i + 1}</span>
                <PositionBadge pos={b.position} />
                <span className="flex-1 font-medium">{b.name}</span>
                <span className="text-muted text-xs">{b.team}</span>
                <div className="flex gap-1">
                  <button
                    className="btn-ghost px-2 py-1"
                    onClick={() => toTop(i)}
                    title="Move to top"
                  >
                    ⤒
                  </button>
                  <button
                    className="btn-ghost px-2 py-1"
                    onClick={() => move(i, -1)}
                    title="Up"
                  >
                    ↑
                  </button>
                  <button
                    className="btn-ghost px-2 py-1"
                    onClick={() => move(i, 1)}
                    title="Down"
                  >
                    ↓
                  </button>
                  <button
                    className="btn-ghost text-danger px-2 py-1"
                    onClick={() => remove(i)}
                    title="Remove"
                  >
                    ✕
                  </button>
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}
