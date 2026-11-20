---
# gstack: design-md-format=spec
name: OpsGraph CALIBRATION
colors:
  paper: "#F7F5F0"
  surface: "#FFFFFF"
  sunk: "#ECE8DF"
  ink: "#1B1A17"
  inkMuted: "#6B6459"
  hairline: "#DEDACF"
  grid: "#E7E3D8"
  spec: "#1F3FA0"
  drift: "#E8490F"
  pass: "#1B7F4E"
  reject: "#C73E1D"
  passTint: "#C9DCCD"
  driftTint: "#F3DDD0"
typography:
  display: "Cabinet Grotesk"
  body: "Instrument Sans"
  data: "JetBrains Mono"
  heroHeadline: "52px/800/-0.01em"
  readinessNumeral: "170px/800/-0.03em"
  sectionHead: "26px/700"
  bodyText: "15px/400 lh1.55"
  dataTag: "11px mono ls0.05em"
rounded:
  default: "0px"
  max: "2px"
spacing:
  base: "8px"
  module: "24px"
  rowPaddingY: "12px"
  sectionGap: "48-96px"
  pageMarginMin: "40px"
components:
  tag: "bracketed mono, 1px semantic border, 11px"
  certificateHeader: "11px mono doc line on hairline"
  gauge: "flat line-art dial, marketing only"
  readinessNumeral: "flat display figure + tolerance rule, product only"
  specimenObserved: "sunk well, off-grid rows, orange flag diamonds"
  specimenRequired: "grid-backed ordered taxonomy, spec-blue numbers"
  button: "mono-bracketed [ LABEL ], ink fill primary / hairline ghost"
---

# OpsGraph Design System — CALIBRATION

A measuring-instrument aesthetic on warm paper. OpsGraph is not a dashboard; it is
a calibration instrument for a company's operating structure. Every mark either
measures something, flags something, or certifies something. Decoration that does
none of these does not ship.

First impression target: **relief** — a held breath released. The visitor sees
their own chaos recognized and measured, which makes it fixable.

---

## 1. Visual thesis

OpsGraph sells the feeling of a needle settling into the green. The product
already speaks metrology: it measures a workspace against a required-state
standard, tracks drift, reports readiness, and keeps a decision ledger. The
design system renders that literal truth — instruments, tolerances, specimens,
certificates — instead of borrowing the compliance-SaaS dashboard vocabulary
(Vanta purple, stat cards, hero-screenshot-of-own-UI).

**Semantic color contract (the whole system):**

- **Spec blue** = required / canonical state — what should exist
- **Flag orange** = drift / out-of-tolerance — what is wrong
- **Tolerance green** = in-spec / passed / approved — what is healthy

Three hues, three meanings, never swapped. Nothing else gets a hue.

## 2. Color tokens

```css
:root {
  /* Surfaces */
  --og-paper:        #F7F5F0;  /* ground — warm paper, not clinical white */
  --og-surface:      #FFFFFF;  /* panels/cards sit one step whiter */
  --og-sunk:         #ECE8DF;  /* inset wells — OBSERVED/before panels only */

  /* Ink */
  --og-ink:          #1B1A17;  /* primary text, instrument lines */
  --og-ink-muted:    #6B6459;  /* secondary text, timestamps, captions */

  /* Rules */
  --og-hairline:     #DEDACF;  /* borders, dividers — warm grey, never cool */
  --og-grid:         #E7E3D8;  /* faint engineering grid under REQUIRED data */

  /* Semantics — the only hues */
  --og-spec:         #1F3FA0;  /* required/canonical — blueprint blue */
  --og-drift:        #E8490F;  /* flagged drift — flagging-tape orange */
  --og-pass:         #1B7F4E;  /* in tolerance / approved — the relief color */
  --og-reject:       #C73E1D;  /* hard failure only — rare */

  /* Tints */
  --og-pass-tint:    #C9DCCD;  /* behind approved/pass rows */
  --og-drift-tint:   #F3DDD0;  /* behind drift-flagged rows */
}
```

Hard rules:

- No purple anywhere in any role (Vanta owns it in this category).
- No gradients, no glow, no shadows except a single 1px inset on `--og-sunk`.
- `--og-drift` and `--og-reject` are never used decoratively or adjacently.
- Light mode only for v1. Do not add a dark theme.

## 3. Typography

Three families, one job each. No serif, no italics — instruments do not
italicize.

| Role | Family | Source | Usage |
|---|---|---|---|
| Display | **Cabinet Grotesk** | Fontshare (free, ITF FFL) | Headlines, the readiness numeral. Weights 500–800. Pinched joins give it a stamped, industrial feel. |
| Body | **Instrument Sans** | Google Fonts (OFL) | Prose, sub-heads, descriptions. Weights 400–600. |
| Data | **JetBrains Mono** | Google Fonts (OFL) | ALL artifact IDs, file names, statuses, tags, readouts, timestamps, the certificate header. |

```css
--og-font-display: "Cabinet Grotesk", sans-serif;
--og-font-body:    "Instrument Sans", sans-serif;
--og-font-data:    "JetBrains Mono", monospace;
```

Type scale (display / body):

- Hero headline: 52px / 800 / -0.01em tracking (Cabinet Grotesk)
- Readiness numeral: 120–170px / 800 / -0.03em (Cabinet Grotesk)
- Section heads: 24–28px / 700
- Body: 15–16px / 400–500, line-height 1.55
- Data rows & tags: 11–12px JetBrains Mono, letter-spacing 0.03–0.06em

Premium upgrade paths (only if licensed later): display → PP Formula Condensed;
body → Söhne or National 2; data → Berkeley Mono.

## 4. The tag system (signature component)

All status, classification, and honesty markers render as **bracketed mono
tags** — the product's own `[simulation]` honesty syntax becomes the label
system. Brackets are drawn, not typed:

```html
<span class="tag pass">[IN TOLERANCE]</span>
<span class="tag drift">[DRIFT +12]</span>
<span class="tag sim">[SIMULATION]</span>
```

- 11px JetBrains Mono, 1px border in the semantic color, 2px/7px padding.
- `[SIMULATION]` gets a stippled/muted treatment and **never animates** —
  stillness signals "this did not really happen."
- Tags replace icon-and-label badges entirely. No icon library above headings.

## 5. Readiness displays (contextual)

**Landing & marketing: the gauge.** A flat line-drawn dial — 2px ink arc, tick
marks, single needle settling into a green tolerance arc. Strictly flat
line-art; no chrome, no skeuomorphism. The needle's settle is the brand moment.

**Dashboard & daily use: the numeral.** A large flat Cabinet Grotesk figure
(120–170px) presented like a bank-statement balance, with a thin rule beneath
whose terminal quarter is `--og-pass` — the tolerance band implied, not drawn.
Calmer for repeated viewing.

## 6. Layout

- **Asymmetric field-sheet.** Nothing important is centered. Headlines and
  CTAs live left-aligned in the margin, like a title block on an engineering
  drawing.
- **Certificate header.** Every primary surface carries a slim document header:
  `CERT <company-id> · REV <n> · <legal name>` in 11px JetBrains Mono on a
  hairline — the product framing itself as an issued instrument.
- **The transformation is the hero.** Wherever the product's value must be
  shown, use the paired specimen frames:
  - `[OBSERVED]` — the customer's real mess: dense mono file list, rows
    nudged off-grid (±5–14px translate, ±0.6° rotate), orange flag diamonds on
    flagged items, `--og-sunk` background.
  - `[REQUIRED]` — the canonical taxonomy: same mono size, perfectly ordered,
    numbered rows in `--og-spec`, faint `--og-grid` lines behind.
  The mess is contained in its frame as the *object of measurement* — it must
  never read as OpsGraph's own chrome being sloppy.
- **Data is dense in tight rows; the page is generous.** 12px vertical padding
  on ledger rows; 48–96px between major sections; page margins ≥40px desktop.

## 7. Spacing

8px base unit; 24px grid module for macro layout.

```
4  8  12  16  24  32  48  64  96
```

- Nothing tighter than 16px between two text blocks.
- Ledger/table rows: 12px vertical padding, hairline row dividers only.
- Component internal padding: 8–12px. Section gaps: 48–96px.

## 8. Motion

Mechanical, diegetic, brief. Motion must feel like an instrument actuating —
a stamp hitting paper, a needle settling — never like SaaS micro-interactions.

- **Needle/gauge:** spring settle with ~4% detent overshoot, ~220ms.
- **State changes:** step-change at 180–220ms. A resolved artifact's row flips
  its flag diamond orange→green and slides horizontally into place — one
  movement, no bounce, no fade.
- **Flag marks:** peel/stamp in, never fade or grow.
- **`[SIMULATION]` tags and everything simulated:** zero animation, always.
- No parallax, no scroll-jacking, no cross-fades between sections.
- `prefers-reduced-motion`: all motion becomes instant step-change; the needle
  renders already settled.

## 9. Surfaces

- Hairlines (`--og-hairline`) are the only dividers. No card-in-card nesting;
  a panel is one hairline box, not a rounded container inside another.
- Corner radius: 0–2px everywhere. Instruments have square corners.
- Buttons are mono-bracketed: `[ REQUEST PILOT ]` — ink fill for primary,
  hairline ghost for secondary. Never pill-shaped.

## 10. Accessibility

- `--og-ink` on `--og-paper` ≈ 14.5:1; `--og-ink-muted` on `--og-paper` ≈ 4.8:1
  (AA for small text).
- `--og-drift` on `--og-paper` ≈ 3.2:1 — flags, large text, and bordered tags
  only; never body copy. On orange fills, use `--og-ink` text.
- `--og-pass`, `--og-spec`, `--og-reject` all pass AA on `--og-paper` for text.
- Semantic colors always paired with a non-color cue: flag diamonds, tag text,
  row position — drift is never conveyed by orange alone.
- Min body size 14px; data rows may go to 11px mono only where density is the
  point and content is non-prose.

## 10a. Illustration & interactive instruments

- On web surfaces, instruments may be live: isometric line-figures built with
  `@lucasmarkes/hairline` — gauges, file cabinets, and registers that answer the
  pointer. Line-art only; the figures are drawing, not chrome.
- Print and static surfaces keep the same instruments as still line drawings.
- Never photo illustration, 3D renders, or stock imagery — figures are always
  drawn as objects being measured.

## 10b. Voice (copy rules)

- Measure, don't warn — "12 artifacts drifted", never "risk detected".
- State, don't sell — the certificate certifies; it never argues.
- Honest marks — anything simulated, pending, or previewed is tagged
  `[SIMULATION]` and never animates.

## 10c. Components (product UI spec)

- **Ledger row** — the canonical data row: 36px, hairline separators, no row
  fill except the flagged row (sunk-paper `#F3F0E9` + `◆` diamond, never a
  full orange bar). Artifact IDs render spec blue — the reference, not the
  alarm. One accent per row.
- **Actions** — mono-bracketed, two weights only: ink fill = the consequential
  move, hairline ghost = inspection, dashed = gated/unavailable. Never pills,
  never shadows, never two fills in one row.
- **Status tags** — outlined brackets, never filled; the text is the signal.
  Dashed border reserved for `[SIMULATION]` / not-real output.
- **Fields** — hairline underlines, not boxed inputs. Errors tint the rule
  reject-red with a one-line Instrument Sans note.
- **Chart** — the tolerance band: one ink baseline, muted bars, pass-green
  only inside the band. Flat bars; no gradients, no donut charts.
- **States** — left-border strips (green = recorded, orange = drift) and a
  dashed `[NO GAPS]` empty state that stays empty on purpose.

## 10d. Motion (mechanical, not fluid)

- **Tokens**: `detent` 90ms steps(1,end) — state flips · `settle` 200ms
  cubic-bezier(.2,.9,.3,1) — needle/values · `sweep` 320ms
  cubic-bezier(.16,1,.3,1) — observed→required snap · `still` ∞ — simulation.
- **Four moves that exist**: needle settle (one overshoot max), flag step
  (instant, not fade), observed→required snap (the relief moment, once per
  view), pointer-answering instruments via `@lucasmarkes/hairline` (web only).
- **The law**: `[SIMULATION]` and dry-run output never animate — motion =
  real data, stillness = not real yet.
- Honor `prefers-reduced-motion` — needle jumps to value, snap becomes a swap.
- Never: springy easings, number tickers, skeleton shimmer, motion on the
  certificate.

## 10e. Templates (the field kit)

- **Deck** — 16:9, certificate header top, one claim left, rev/date/confidential
  footer. No bullet walls.
- **Doc / one-pager** — portrait, spec header + version, facts always in the
  ledger table, findings as left-rule blocks.
- **Social / OG card** — 1200×630, the only sanctioned dark surface: ink
  field, paper text, the quiet numeral + one status tag.
- **Icons** — the mark drops to its essence (dial dot + band) below 24px;
  ticks die at small size, the essence survives.

## 10f. Website (production specimen — board 11)

- **Page architecture** — certificate strip (CERT OG-001 · REV B /
  INSTRUMENT OF OPERATIONAL READINESS) → nav (mark lockup, Instrument Sans
  links, `[ REQUEST PILOT ]` ink-fill CTA) → asymmetric hero →
  observed/required transformation → four-step method strip → mono footer.
- **Hero** — headline left ("Operational infrastructure, measured."),
  line-drawn gauge right on `sunk` ground; `[IN TOLERANCE]`/`[DRIFT +12]`
  tags beneath the numeral.
- **Method strip** — four columns, mono step tags `01 — SCAN` … `04 —
  GUARD`, hairline dividers; GUARD's tag is `pass`, the rest `spec`.
- **App surface** — the same system at dashboard width: numeral + tolerance
  band left rail (340px), drift ledger right; flagged rows on `sunk` with ◆;
  `[SIMULATION]` dashed tag on pending/simulated rows; audit line + `[
  APPROVE PLAN ]` footer.

## 10g. Mobile (390px specimens — board 12)

- **Priority order** — numeral leads, ledger compresses, tags hold meaning;
  nothing else competes above the fold.
- **Dashboard** — numeral 72px, tolerance band 5px, ledger rows single-line
  truncated, full-width `[ REVIEW DRIFT ]` ink CTA.
- **Drift event** — artifact ID + `[CATEGORY]` tag in chrome; proposal card
  always carries its `[SIMULATION]` dashed tag; actions are `[ APPROVE ]`
  (ink) / `[ DISMISS ]` (ghost).
- **Approvals** — decision rows with action type in muted mono (`compile` /
  `remediate` / `reverse`); destructive confirmation uses `reject` fill
  (`[ CONFIRM ]` on #C73E1D) — the only place red is a fill, not an
  outline.
- **Chrome** — 1.5px ink viewport frame; Instrument Sans chrome text; safe
  single-column throughout.

## 10h. Assets (what ships)

Real, versioned exports live in this repo; the Paper manifest (board 07)
names the same set. Nothing external ships from a screenshot.

- `docs/design/mark/mark-primary.svg` — full mark: dial, five ticks, needle,
  dot. Display size.
- `docs/design/mark/mark-symbol.svg` — small-size essence: dial, needle, dot.
  Nav, favicon source, <24px.
- `docs/design/mark/mark-reversed.svg` — paper-on-ink for the OG card and any
  sanctioned dark surface.
- `docs/design/tokens.json` — color, font, motion, and the hue/simulation/
  surface/reject contracts as data; matches the board 07 tokens block.
- `docs/design/favicon/{16,32}.png` — rasterized from the mark essence;
  heavier stroke, paper ground (readable in dark browser chrome).
- Certificate PDF pending a real template.

## 11. Banned / never-ship list

Purple in any role · gradients · glow/neon · near-black dark mode · pill
buttons · icon tiles above headings · kickers/eyebrow labels (tags replace
them) · decorative blobs/dividers · centered hero layouts · card-in-card
nesting · serif fonts · italics · donut/progress-ring charts · animated
simulation markers · more than one accent in a component.

## 12. Decision log

| Decision | Choice | Source |
|---|---|---|
| Base metaphor | Measuring instrument / calibration, not ledger | In-host outside voice — stronger native fit; avoids the overused "broadsheet ledger" trope the register direction risked |
| Ground color | Warm paper `#F7F5F0` | Claude Code voice — warmth carries "relief"; distinguishes from Attio cool-white and all near-black competitors |
| Label system | Bracketed mono tags | In-host voice — maps to the product's literal `[simulation]`/`[drift]` honesty syntax |
| Semantic hues | Blue/orange/green = required/drift/pass | In-host voice; adopted as a strict contract |
| Readiness display | Gauge on marketing, numeral in product | User decision — dial where drama earns its place, quiet figure where the number is read daily |
| Type stack | Cabinet Grotesk / Instrument Sans / JetBrains Mono | All free and verified loadable; replaces Claude Code's banned-display Fraunces and paid Söhne/Berkeley |
| Light mode only | v1 | Kills the category's dark-glow temptation entirely |
| Interactive figures | `@lucasmarkes/hairline` line-instruments on web | User suggestion — pointer-responsive line-art fits the instrument metaphor without adding chrome |
| Paper brand kit | `OpsGraph — Brand Identity Kit` (13 boards) | Visual source of truth alongside this file; tokens sync both directions |
| Component spec | Ledger row 36px, bracket actions, outlined tags, hairline fields | Kit board 08 — production tokens, not mood |
| Motion | Mechanical detents; stillness = not-real | Kit board 09 — instrument movement, not fluid easing |
| Templates | Deck/doc/OG-card/icon as locked starting points | Kit board 10 — four artifacts that carry the brand |
| Web surfaces | Landing hero (gauge) + app dashboard (numeral) at production width | Kit board 11 — page architecture locked: cert strip → hero → transformation → method → footer |
| Mobile | Numeral leads; reject-fill only on destructive confirm | Kit board 12 — three 390px specimens: dashboard, drift event, approvals |
| Mark assets | SVG exports in `docs/design/mark/` | Governance manifest made real — mark ships as files, not screenshots |

*Researched: Vanta, Linear, Attio, Plain (Drata bot-walled). Category converges
on dense vigilance marketing; nobody sells relief. OpsGraph's differentiator is
the transformation itself rendered as the hero.*
