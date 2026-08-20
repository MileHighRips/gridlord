export default function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      <defs>
        <linearGradient id="glg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#FFD264" />
          <stop offset="1" stopColor="#E9A114" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="14" fill="#0A0E14" />
      <rect
        x="1.5"
        y="1.5"
        width="61"
        height="61"
        rx="12.5"
        fill="none"
        stroke="#232B3A"
        strokeWidth="1.5"
      />
      <path d="M16 40 L13 20 L23 28 L32 15 L41 28 L51 20 L48 40 Z" fill="url(#glg)" />
      <rect x="16" y="42" width="32" height="6" rx="2" fill="url(#glg)" />
      <g stroke="#0A0E14" strokeWidth="2" strokeLinecap="round">
        <line x1="32" y1="30" x2="32" y2="38" />
        <line x1="29" y1="32" x2="35" y2="32" />
        <line x1="29" y1="35" x2="35" y2="35" />
      </g>
    </svg>
  );
}
