// INCOIS Official Logo SVG Component
// Indian National Centre for Ocean Information Services (Ministry of Earth Sciences)

export default function IncoisLogo({ className = 'w-9 h-9' }: { className?: string }) {
  return (
    <div className={`relative flex items-center justify-center rounded-full bg-white shadow-md border border-slate-300 overflow-hidden flex-shrink-0 ${className}`}>
      <svg
        viewBox="0 0 100 100"
        className="w-full h-full"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Outer Circular Ring */}
        <circle cx="50" cy="50" r="48" fill="#ffffff" stroke="#003366" strokeWidth="3.5" />
        <circle cx="50" cy="50" r="44" fill="none" stroke="#008080" strokeWidth="1" strokeDasharray="2,2" />

        {/* Ocean Waves Backdrop */}
        <path
          d="M 10 52 Q 25 44 40 52 T 70 52 T 90 52 L 90 85 Q 70 88 50 85 T 10 85 Z"
          fill="#0284c7"
          opacity="0.25"
        />
        <path
          d="M 8 62 Q 28 54 48 62 T 88 62 L 88 88 Q 68 91 48 88 T 8 88 Z"
          fill="#0369a1"
          opacity="0.45"
        />
        <path
          d="M 8 70 Q 28 62 48 70 T 88 70 L 88 92 Q 68 95 48 92 T 8 92 Z"
          fill="#075985"
        />

        {/* Global Longitude/Latitude lines */}
        <ellipse cx="50" cy="40" rx="36" ry="24" fill="none" stroke="#0284c7" strokeWidth="1.2" opacity="0.6" />
        <ellipse cx="50" cy="40" rx="20" ry="24" fill="none" stroke="#0284c7" strokeWidth="1.2" opacity="0.6" />
        <line x1="14" y1="40" x2="86" y2="40" stroke="#0284c7" strokeWidth="1.2" opacity="0.6" />
        <line x1="50" y1="16" x2="50" y2="64" stroke="#0284c7" strokeWidth="1.2" opacity="0.6" />

        {/* Indian Flag Tri-color Accent Arc */}
        <path
          d="M 28 26 A 28 28 0 0 1 72 26"
          fill="none"
          stroke="#ff9933"
          strokeWidth="2.5"
          strokeLinecap="round"
        />

        {/* Center INCOIS Bold Typography */}
        <text
          x="50"
          y="50"
          textAnchor="middle"
          fill="#002b49"
          fontSize="15"
          fontWeight="900"
          fontFamily="system-ui, -apple-system, sans-serif"
          letterSpacing="0.8"
        >
          INCOIS
        </text>

        {/* Small subtitle arc / wave detail */}
        <path
          d="M 32 54 Q 50 60 68 54"
          fill="none"
          stroke="#008080"
          strokeWidth="2"
          strokeLinecap="round"
        />

        {/* MoES tiny text */}
        <text
          x="50"
          y="82"
          textAnchor="middle"
          fill="#ffffff"
          fontSize="6.5"
          fontWeight="bold"
          fontFamily="sans-serif"
          letterSpacing="0.5"
        >
          MoES INDIA
        </text>
      </svg>
    </div>
  );
}
