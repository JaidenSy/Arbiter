/**
 * HeroBackground — Static dark background for the Arbiter landing hero.
 *
 * Replaces the former WebGL particle network + shader gradient.
 * A subtle radial glow from the top center is sufficient.
 */

export default function HeroBackground() {
  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden" aria-hidden>
      {/* Layer 1 — Base dark surface */}
      <div className="absolute inset-0 bg-[#0A0A0B]" />

      {/* Layer 2 — Dot grid texture, fades out at 65% height */}
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24'%3E%3Ccircle cx='12' cy='12' r='1' fill='rgba(61%2C53%2C206%2C0.30)'/%3E%3C/svg%3E\")",
          backgroundRepeat: 'repeat',
          backgroundSize: '24px 24px',
          maskImage: 'linear-gradient(to bottom, rgba(0,0,0,1) 0%, rgba(0,0,0,0.9) 40%, rgba(0,0,0,0) 65%)',
          WebkitMaskImage: 'linear-gradient(to bottom, rgba(0,0,0,1) 0%, rgba(0,0,0,0.9) 40%, rgba(0,0,0,0) 65%)',
        }}
      />

      {/* Layer 3 — Indigo radial glow, sits above texture */}
      <div
        className="absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse 80% 50% at 50% -20%, rgba(61,53,206,0.18) 0%, transparent 70%)',
        }}
      />
    </div>
  )
}
