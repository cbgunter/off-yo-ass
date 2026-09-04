# Off Yo Ass — Branding Guidelines

Instructions for implementing the UI. Follow these literally. When a choice isn't
covered here, pick the plainer option.

## The one rule

The product is anti-gamification. The interface must look **unimpressed**. No
streaks, badges, points, confetti, progress rings, trophies, celebration states,
or encouraging exclamation marks. A number and its baseline is the entire design
language. If a component would make someone feel congratulated, delete it.

## Palette

Warm paper, not white. Warm ink, not black. One accent.

```css
:root {
  /* Surfaces */
  --paper:      #F5F2EC;  /* app background */
  --paper-sunk: #EFEBE3;  /* inset rows, table stripes */
  --rule:       #DDD7CB;  /* hairlines, dividers, borders */

  /* Text */
  --ink:        #26231E;  /* headlines, primary numbers */
  --ink-soft:   #5A554B;  /* body copy */
  --ink-faint:  #8C8578;  /* labels, units, timestamps */

  /* Accent — one, used sparingly */
  --clay:       #B4593C;  /* prescription, active state, the call */
  --clay-sunk:  #F0DED6;  /* accent fill behind text */

  /* Signal — only for baseline deltas, never decoration */
  --above:      #4A6B4F;  /* better than baseline */
  --below:      #9A5238;  /* worse than baseline */
}
```

Rules:

- `--clay` appears **at most twice per screen**. It marks tonight's prescription
  and the primary action. Nothing else.
- `--above` / `--below` are for delta text and 1px sparkline strokes only. Never
  fill a card with them. Never use red/green as a verdict on the person.
- Dark mode: not in v1. Ship warm-light only.
- No gradients anywhere. No shadows anywhere. No glows, no glass, no blur.

## Type

Two families. Load from Google Fonts.

```css
--font-display: 'Instrument Serif', Georgia, serif;   /* 400 only */
--font-text:    'IBM Plex Sans', system-ui, sans-serif;
--font-mono:    'IBM Plex Mono', ui-monospace, monospace;
```

| Role | Family | Size / line-height | Notes |
|---|---|---|---|
| Screen title | display | 34 / 1.1 | Sentence case |
| The headline (coach's blunt line) | display | 28 / 1.25 | Contains a real number |
| Big metric | mono | 44 / 1.0 | `font-variant-numeric: tabular-nums` |
| Metric label | text | 12 / 1.2 | Uppercase, `letter-spacing: 0.08em`, `--ink-faint` |
| Delta vs baseline | mono | 13 / 1.2 | `−12%` / `+0.4` with sign, then `vs 30d` |
| Body | text | 15 / 1.5 | `--ink-soft`, `text-wrap: pretty` |
| Button | text | 15 / 1 | Weight 500, sentence case |
| Timestamp / unit | mono | 12 / 1.2 | `--ink-faint` |

- Serif is for **headlines and titles only**. Never for data, labels, or buttons.
- All numerals are mono with tabular figures so columns don't jitter on sync.
- Sentence case everywhere except metric labels. No Title Case. No ALL CAPS
  outside 12px labels.

## Space and shape

- Spacing scale: `4, 8, 12, 16, 24, 32, 48, 64`. Nothing between.
- Screen padding: 20px horizontal, 24px top.
- Corner radius: **2px** on buttons and inputs. **0** on everything else. No
  rounded cards.
- Separation comes from 1px `--rule` hairlines and whitespace. Not from cards,
  borders-on-four-sides, or elevation.
- Generous vertical rhythm — a screen with six metrics and lots of air beats a
  screen with twelve packed ones.

## Components

**Metric row.** Label above, big mono number, unit in `--ink-faint`, delta to the
right, optional 1px sparkline. Separated from siblings by a hairline, not a card.

```
SLEEP
7h 12m          −38m vs 30d
────────────────────────────
```

**The Call (15:45).** The only screen that leads with serif at full size. Order:
headline → prescription → why → fallback. The prescription is the one `--clay`
element: activity, duration, intensity, window, set in text at 17px on
`--clay-sunk`. `why` is body copy citing the actual numbers. `fallback` sits
below a hairline in 13px `--ink-faint`. When `skip_ok` is true, the headline says
rest and there is no primary button.

**Check-in (20:30).** Three equal-width buttons — Did it / Partial / No. Same
visual weight; the app has no opinion until it has data. Outline, 2px radius,
1px `--rule`, `--ink` label. Pressed state fills `--clay-sunk`.

**Buttons.** Primary: `--clay` fill, `--paper` label. Secondary: transparent with
1px `--rule`. Minimum height 48px, minimum touch target 44px. Full-width on
phone. Max one primary per screen.

**Quick-log.** Yard work, wood splitting, garden walking, manual BP get the same
treatment as Peloton and rowing. No secondary styling, no "other" bucket. They
are prescriptions, not consolation prizes.

**Receipts (Sunday).** Plain tables and 1px line charts. Hairline rules, tabular
figures, no fills, no legends where a direct label works. Correlations stated as
sentences with numbers, not as scores or grades.

## Charts

- 1px strokes, `--ink` or the delta color. No area fills, no gradients, no dots
  except the current value.
- Baseline drawn as a dashed 1px `--rule` line, always labelled.
- Axes: hairline, `--ink-faint`, 12px mono. No gridlines beyond the baseline.

## Icons

Almost none. Where unavoidable, 1.5px stroke line icons, `currentColor`, 20px.
No filled icons, no duotone, no illustration, no emoji.

## Copy

Matter-of-fact and short. State the number, state the prescription, stop.

- Do: "HRV is 12% under your baseline. 40 minutes walking, easy, 17:30–18:30."
- Don't: "Let's take it easy today! 💪 Your body is asking for recovery."

No second-person cheerleading, no metaphors about journeys, no rhetorical
questions, no em-dash flourishes. Never editorialize about golf, beer, or a
missed session — show what the numbers did and stop there.

Error and empty states are declarative: "Garmin tokens expired. Re-auth on your
laptop." not "Oops! Something went wrong."

## Mobile PWA

- Design at 390px wide first. Everything works one-handed.
- Respect `env(safe-area-inset-*)`.
- Body text never below 15px; labels never below 12px; touch targets never below
  44px.
- Offline shell uses the same paper background — no skeleton shimmer, no spinner
  animation. Show last-synced timestamp in mono `--ink-faint` instead.
- Push notification copy is the coach's `headline` verbatim, unmodified.

## Do not

Gradient backgrounds · shadows and elevation · rounded cards · left-border accent
strips · glass or blur · emoji · progress rings · streak counters · celebration
animations · red/green as judgement · Inter, Roboto, or Arial · more than one
accent color · Title Case · exclamation marks.
