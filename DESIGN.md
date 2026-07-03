# ArbiterAI — Design System

## Theme
Dark primary (default). Light mode supported via `data-theme="light"`. All components must work in both.
Dark scenes: developer at a monitor, dim room, extended session. Dark is not an aesthetic choice — it's the correct answer for this user.

## Color Strategy
**App surfaces**: Restrained — zinc base + amber accent for primary actions and state only.
**Landing hero**: Committed — amber aurora gradient carries the page, teal as data signal.

### Dark Theme Tokens
```
--color-base:          #0A0A0B   /* page background */
--color-surface:       #111113   /* cards, panels */
--color-elevated:      #18181B   /* raised elements, dropdowns */
--color-highlight:     #27272A   /* hovered rows, selected states */
--color-overlay:       #141416   /* modal backdrops */

--color-accent:        #D97706   /* amber — primary CTA, active nav, key actions */
--color-accent-light:  #F59E0B   /* hover/lift state */
--color-accent-dim:    #78350F   /* recessive amber foreground */
--color-accent-wash:   #1C1410   /* amber tint surface (use sparingly) */

--color-teal:          #14B8A6   /* cache hit, success signal, data viz */
--color-teal-light:    #5EEAD4   /* teal hover/highlight */

--color-primary:       #FAFAFA   /* headings, primary text */
--color-secondary:     #A1A1AA   /* body text, labels */
--color-muted:         #52525B   /* placeholders, disabled text */

--color-error:         #F87171
--color-success:       #34D399
--color-warning:       #FBBF24

--color-border:        rgba(255,255,255,0.07)
--color-border-strong: rgba(255,255,255,0.12)
--color-border-accent: rgba(217,119,6,0.35)
```

### Light Theme Tokens
```
--color-base:          #FAFAF9
--color-surface:       #FFFFFF
--color-elevated:      #F4F4F5
--color-accent:        #B45309   /* amber-700 */
--color-accent-light:  #D97706
--color-primary:       #18181B
--color-secondary:     #52525B
--color-muted:         #A1A1AA
```

### Glow Ladder
Four rungs of amber luminance for interactive depth. Use sparingly.
```
--glow-none:     none
--glow-subtle:   0 0 12px rgba(217,119,6,0.10)
--glow-standard: 0 0 20px rgba(217,119,6,0.22)
--glow-hero:     0 0 32px rgba(217,119,6,0.40), 0 0 64px rgba(217,119,6,0.15)
```
Teal glow for cache/success: `0 0 12px rgba(20,184,166,0.10)`.

## Typography
| Role | Font | Size | Weight | Notes |
|---|---|---|---|---|
| Display / H1 | Geist | 2.25rem+ | 700 | letter-spacing: -0.014em, ss01 |
| Headings H2–H4 | Geist | 1.5rem–1.125rem | 600 | same tracking |
| Body / Prose | Inter | 14px | 400 | line-height: 1.6, cv11/cv06/ss01 |
| Labels / UI | Inter | 12–13px | 500 | tighter, secondary color |
| Monospace | JetBrains Mono / Fira Code | inherit | 400 | for keys, traces, code |

- Cap prose line length at 65–75ch.
- Never use Geist in buttons, form labels, table cells, or dense UI. Inter carries all product UI.
- Hierarchy through scale + weight. Avoid flat scales.

## Spacing
- **Landing sections**: `py-24 px-6` vertical rhythm between sections, `max-w-5xl mx-auto` content width
- **App cards / panels**: `p-5` or `p-6`
- **Compact rows (tables, lists)**: `px-4 py-2` or `px-4 py-3`
- Vary spacing for rhythm. Same padding everywhere is monotony.

## Elevation Stack
base → surface → elevated → highlight → overlay (low → high)
Use `bg-surface`, `bg-elevated`, `bg-highlight` — never hardcode hex values in components.

## Component States
Every interactive element must have: default, hover, focus, active, disabled, loading, error.
- Skeleton loaders for async content (not spinners in the middle of content areas)
- Empty states that explain the interface, not just "Nothing here"

## Tile System
Four ambient-gradient tile variants via CSS classes:
- `.tile-amber` — amber radial gradient (security events, key cards)
- `.tile-teal` — teal radial gradient (cache, success, data)
- `.tile-warning` — yellow gradient (quota, rate limit)
- `.tile-error` — red gradient (blocked calls, auth failures)

## Motion
- Easing: `ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1)` — use for entries and reveals
- Easing: `ease-out-quart: cubic-bezier(0.25, 1, 0.5, 1)` — use for hovers and state changes
- Durations: instant 100ms, fast 150ms, base 220ms, slow 320ms
- No bounce, no elastic, no choreographed page-load sequences
- Motion signals state — not decoration. Enter/exit, feedback, loading reveal: nothing else.

## Icons
**lucide-react only.** Never emoji. Never custom SVGs unless lucide doesn't have it.
Size: 14px in UI labels, 16px in buttons/nav, 20px+ in empty states/heroes.

## Absolute Bans
- Side-stripe borders as decoration
- Gradient text (`background-clip: text`)
- Floating orbs or decorative blurs
- Glassmorphism used decoratively
- Identical card grids with generic icons
- Em dashes in copy (use colons, commas, semicolons)
- Emoji anywhere in the UI
- Display font (Geist) in buttons or dense UI labels
