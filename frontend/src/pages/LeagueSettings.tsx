import { useEffect, useState } from 'react';
import { api, LeagueSettings as LS } from '../api/client';

const POSITIONS = ['QB', 'RB', 'WR', 'TE', 'FLEX', 'SUPERFLEX', 'K', 'DEF'];

const VINNY_LEAGUE_PRESET: LS = {
  leagueName: '2026 League',
  teams: 12,
  season: 2026,
  scoring: {
    type: 'PPR',
    rules: {
      pass_yd: 0.04,
      pass_td: 4,
      interception: -2,
      rush_yd: 0.1,
      rush_td: 6,
      reception: 1,
      rec_yd: 0.1,
      rec_td: 6,
      two_pt: 2,
      fumble_lost: -2,
      off_fum_ret_td: 6,
      fg_0_19: 3,
      fg_20_29: 3,
      fg_30_39: 3,
      fg_40_49: 4,
      fg_50_plus: 5,
      fg_miss_0_19: -3,
      fg_miss_20_29: -3,
      fg_miss_30_39: -3,
      fg_miss_40_49: -3,
      fg_miss_50_plus: -3,
      pat_made: 1,
      pat_miss: -1,
      sack: 1,
      def_int: 2,
      fum_rec: 2,
      def_td: 6,
      safety: 2,
      block_kick: 3,
      def_return_td: 6,
      xp_returned: 2,
    },
  },
  roster: {
    starters: { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, K: 1, DEF: 1 },
    bench: 7,
    ir_slots: 1,
  },
  waiver: {
    type: 'rolling',
    budget: 100,
    reset: 'weekly',
    process_day: 'Tuesday',
    clear_days: 2,
  },
  trades: {
    review: 'commissioner',
    veto_votes: 5,
    reject_days: 1,
    deadline: '2026-12-02',
    allow_draft_pick_trades: false,
  },
  keepers: { count: 0, cost_increase: null },
  playoff_teams: 6,
  playoff_start_week: 15,
  playoff_end_week: 17,
  fractional_points: true,
  negative_points: true,
};

// Live, no-JSON league editor. Loads the current league, edits inline, saves via PUT.
export default function LeagueSettings() {
  const [leagueId, setLeagueId] = useState<number | null>(null);
  const [s, setS] = useState<LS | null>(null);
  const [defaultSettings, setDefaultSettings] = useState<LS | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [showJson, setShowJson] = useState(false);
  const [rawJson, setRawJson] = useState('');
  const [provider, setProvider] = useState('sleeper');

  useEffect(() => {
    (async () => {
      try {
        const lg = await api.myLeague();
        setLeagueId(lg.id);
        setDefaultSettings(lg.settings);
        setS(lg.settings);
      } catch {
        const d = await api.defaults();
        setDefaultSettings(d);
        setS(d);
      }
    })();
  }, []);

  function applyPreset(name: "Gage's league" | "Vinny's league") {
    const next =
      name === "Gage's league"
        ? (defaultSettings ?? s ?? VINNY_LEAGUE_PRESET)
        : VINNY_LEAGUE_PRESET;
    setS(JSON.parse(JSON.stringify(next)));
    setStatus(`Loaded ${name} preset`);
  }

  function patch(partial: Partial<LS>) {
    setS((prev) => (prev ? { ...prev, ...partial } : prev));
  }
  function setStarter(pos: string, n: number) {
    if (!s) return;
    const starters = { ...s.roster.starters };
    if (n <= 0) delete starters[pos];
    else starters[pos] = n;
    patch({ roster: { ...s.roster, starters } });
  }
  function setScoreType(type: string) {
    if (!s) return;
    const rules = { ...s.scoring.rules };
    if (type === 'PPR') rules.reception = 1;
    else if (type === 'Half-PPR') rules.reception = 0.5;
    else if (type === 'Standard') rules.reception = 0;
    patch({ scoring: { type, rules } });
  }
  function setRule(key: string, val: number) {
    if (!s) return;
    patch({ scoring: { ...s.scoring, rules: { ...s.scoring.rules, [key]: val } } });
  }

  async function save() {
    if (!s) return;
    setStatus('Saving…');
    try {
      if (leagueId) await api.updateLeague(leagueId, s);
      else {
        const created = await api.createLeague(s);
        setLeagueId(created.id);
      }
      setStatus('✓ Saved — rankings now use these rules');
    } catch (e) {
      setStatus((e as Error).message);
    }
  }

  async function doImport() {
    try {
      const res = (await api.importLeague(provider, JSON.parse(rawJson))) as Record<
        string,
        unknown
      >;
      setStatus(`Imported (${Math.round(Number(res.mapping_accuracy) * 100)}% mapped)`);
    } catch (e) {
      setStatus((e as Error).message);
    }
  }

  if (!s) return <p className="text-slate-400">Loading…</p>;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <h1 className="text-xl font-bold">League Settings</h1>
        <div className="flex flex-wrap gap-2">
          <button className="btn-ghost" onClick={() => applyPreset("Gage's league")}>
            Gage's league
          </button>
          <button className="btn-ghost" onClick={() => applyPreset("Vinny's league")}>
            Vinny's league
          </button>
          <button className="btn" onClick={save}>
            Save changes
          </button>
        </div>
      </div>
      {status && <p className="text-gridiron-400 text-sm">{status}</p>}

      <div className="grid gap-4 lg:grid-cols-3">
        <section className="card space-y-3">
          <h2 className="font-bold">Basics</h2>
          <TextField
            label="League name"
            value={s.leagueName}
            onChange={(v) => patch({ leagueName: v })}
          />
          <NumField label="Teams" value={s.teams} onChange={(v) => patch({ teams: v })} />
          <NumField
            label="Season"
            value={s.season}
            onChange={(v) => patch({ season: v })}
          />
          <SelectField
            label="Scoring type"
            value={s.scoring.type}
            options={['PPR', 'Half-PPR', 'Standard', 'Custom']}
            onChange={setScoreType}
          />
          <Toggle
            label="Fractional points"
            checked={s.fractional_points}
            onChange={(v) => patch({ fractional_points: v })}
          />
        </section>

        <section className="card space-y-3">
          <h2 className="font-bold">Roster (starters)</h2>
          <div className="grid grid-cols-2 gap-2">
            {POSITIONS.map((pos) => (
              <NumField
                key={pos}
                label={pos}
                value={s.roster.starters[pos] ?? 0}
                onChange={(v) => setStarter(pos, v)}
              />
            ))}
          </div>
          <NumField
            label="Bench"
            value={s.roster.bench}
            onChange={(v) => patch({ roster: { ...s.roster, bench: v } })}
          />
          <NumField
            label="IR slots"
            value={s.roster.ir_slots}
            onChange={(v) => patch({ roster: { ...s.roster, ir_slots: v } })}
          />
        </section>

        <section className="card space-y-3">
          <h2 className="font-bold">Scoring</h2>
          <NumField
            step={0.5}
            label="Points / reception"
            value={s.scoring.rules.reception ?? 0}
            onChange={(v) => setRule('reception', v)}
          />
          <NumField
            label="Passing TD"
            value={s.scoring.rules.pass_td ?? 4}
            onChange={(v) => setRule('pass_td', v)}
          />
          <NumField
            label="Interception"
            value={s.scoring.rules.interception ?? -2}
            onChange={(v) => setRule('interception', v)}
          />
          <NumField
            label="Rushing TD"
            value={s.scoring.rules.rush_td ?? 6}
            onChange={(v) => setRule('rush_td', v)}
          />
          <NumField
            label="Receiving TD"
            value={s.scoring.rules.rec_td ?? 6}
            onChange={(v) => setRule('rec_td', v)}
          />
          <p className="text-xs text-slate-500">
            Yardage &amp; bonus rules preserved from your league. Use Advanced JSON to
            edit every stat.
          </p>
        </section>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <section className="card space-y-3">
          <h2 className="font-bold">Waivers</h2>
          <SelectField
            label="Type"
            value={s.waiver.type}
            options={['rolling', 'FAAB']}
            onChange={(v) => patch({ waiver: { ...s.waiver, type: v } })}
          />
          <NumField
            label="FAAB budget"
            value={s.waiver.budget}
            onChange={(v) => patch({ waiver: { ...s.waiver, budget: v } })}
          />
        </section>
        <section className="card space-y-3">
          <h2 className="font-bold">Trades</h2>
          <SelectField
            label="Review"
            value={s.trades.review}
            options={['commissioner', 'league_vote', 'none']}
            onChange={(v) => patch({ trades: { ...s.trades, review: v } })}
          />
          <NumField
            label="Reject days"
            value={s.trades.reject_days}
            onChange={(v) => patch({ trades: { ...s.trades, reject_days: v } })}
          />
        </section>
        <section className="card space-y-3">
          <h2 className="font-bold">Playoffs</h2>
          <NumField
            label="Playoff teams"
            value={s.playoff_teams}
            onChange={(v) => patch({ playoff_teams: v })}
          />
          <NumField
            label="Start week"
            value={s.playoff_start_week}
            onChange={(v) => patch({ playoff_start_week: v })}
          />
          <NumField
            label="End week"
            value={s.playoff_end_week}
            onChange={(v) => patch({ playoff_end_week: v })}
          />
        </section>
      </div>

      <section className="card">
        <button className="btn-ghost" onClick={() => setShowJson((v) => !v)}>
          {showJson ? '▾' : '▸'} Advanced: import league JSON
        </button>
        {showJson && (
          <div className="mt-3 space-y-2">
            <div className="flex gap-2">
              <select
                className="input"
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
              >
                {['sleeper', 'espn', 'yahoo', 'nfl', 'manual'].map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
              <button className="btn" onClick={doImport}>
                Import &amp; map
              </button>
            </div>
            <textarea
              className="input h-40 w-full font-mono text-xs"
              placeholder="Paste league JSON…"
              value={rawJson}
              onChange={(e) => setRawJson(e.target.value)}
              spellCheck={false}
            />
          </div>
        )}
      </section>
    </div>
  );
}

function TextField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs text-slate-400">
      {label}
      <input className="input" value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}
function NumField({
  label,
  value,
  onChange,
  step,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  step?: number;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs text-slate-400">
      {label}
      <input
        className="input"
        type="number"
        step={step ?? 1}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  );
}
function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs text-slate-400">
      {label}
      <select className="input" value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => (
          <option key={o}>{o}</option>
        ))}
      </select>
    </label>
  );
}
function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-slate-300">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      {label}
    </label>
  );
}
