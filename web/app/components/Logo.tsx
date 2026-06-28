// Aegis mark — a compass-starburst in the same family as InterOpera's "Nexus"
// logo: a purple→teal gradient four-point sparkle with a teal sparkle behind it
// and a hollow center. Auditable Engine for Graph-Integrated Source-tracking.
export function Logo({ size = 32 }: { size?: number }) {
  const S =
    "M24 2 C 25.5 14 34 22.5 46 24 C 34 25.5 25.5 34 24 46 C 22.5 34 14 25.5 2 24 C 14 22.5 22.5 14 24 2 Z";
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" aria-label="Aegis">
      <defs>
        <linearGradient id="aegisMain" x1="6" y1="4" x2="42" y2="44" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#6562E7" />
          <stop offset="0.5" stopColor="#A5A6F6" />
          <stop offset="1" stopColor="#73DFD7" />
        </linearGradient>
      </defs>
      {/* teal sparkle behind, rotated 45° and scaled down */}
      <path
        d={S}
        fill="#73DFD7"
        opacity="0.55"
        transform="rotate(45 24 24) translate(24 24) scale(0.8) translate(-24 -24)"
      />
      {/* main gradient sparkle */}
      <path d={S} fill="url(#aegisMain)" />
      {/* hollow center diamond */}
      <path d="M24 16.5 L 31.5 24 L 24 31.5 L 16.5 24 Z" fill="#FFFFFF" />
    </svg>
  );
}
