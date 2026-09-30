/** Isotipo: el anillo de progreso (naranja -> esmeralda) con una k dentro. */
export function Logo({ size = 40, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" className={className} aria-hidden>
      <defs>
        <linearGradient id="kcalia-logo" x1="12%" y1="88%" x2="88%" y2="12%">
          <stop offset="0%" stopColor="#ff8a3d" />
          <stop offset="100%" stopColor="#34d399" />
        </linearGradient>
      </defs>
      <circle cx="32" cy="32" r="24" fill="none" stroke="var(--track)" strokeWidth="7" />
      <circle
        cx="32"
        cy="32"
        r="24"
        fill="none"
        stroke="url(#kcalia-logo)"
        strokeWidth="7"
        strokeLinecap="round"
        strokeDasharray="116 151"
        transform="rotate(-90 32 32)"
      />
      <path
        d="M27 22v20M27 34l9-8M30.5 31.5 37 42"
        fill="none"
        stroke="var(--text)"
        strokeWidth="4.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={`font-semibold tracking-[-0.035em] text-text ${className ?? ''}`}>
      <span className="text-accent-text">k</span>calia
    </span>
  )
}
