export const POSITION_COLORS: Record<string, string> = {
  QB: 'bg-rose-500/20 text-rose-300',
  RB: 'bg-emerald-500/20 text-emerald-300',
  WR: 'bg-sky-500/20 text-sky-300',
  TE: 'bg-amber-500/20 text-amber-300',
  K: 'bg-violet-500/20 text-violet-300',
  DEF: 'bg-slate-500/20 text-slate-300',
};

export function posColor(pos: string): string {
  return POSITION_COLORS[pos] ?? 'bg-slate-500/20 text-slate-300';
}
