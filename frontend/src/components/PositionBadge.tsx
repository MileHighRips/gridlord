import { posColor } from '../lib/positions';

export default function PositionBadge({ pos }: { pos: string }) {
  return <span className={`pill ${posColor(pos)}`}>{pos}</span>;
}
