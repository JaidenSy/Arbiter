/**
 * HeroBackground — Static dark background for the Arbiter landing hero.
 *
 * Replaces the former WebGL particle network + shader gradient.
 * A subtle radial glow from the top center is sufficient.
 */

export default function HeroBackground() {
  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden" aria-hidden>
      {/* Base — flat dark surface matching bg-base */}
      <div className="absolute inset-0 bg-[#0A0A0B]" />

      {/* Subtle top-center ambient glow — amber brand color, very low opacity */}
      <div
        className="absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse 80% 50% at 50% -20%, rgba(217,119,6,0.15) 0%, transparent 70%)',
        }}
      />
    </div>
  )
}
