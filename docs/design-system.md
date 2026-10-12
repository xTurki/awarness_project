# Security Awareness Training, UI Design System

**Implementation**: `backend/app/static/css/app.css`, one file, on top of vendored Bootstrap 5.3.3, Bootstrap Icons 1.11.3 and the Inter typeface
**Applied across**: all 35 templates under `backend/app/templates/`
**Contrast**: measured, not asserted. Every ratio below was computed from WCAG relative luminance.

---

## Design foundations

### What the system is for

This is a platform people are told to use by their employer. It is not competing
for attention, and it is read far more often than it is admired. Two decisions
follow from that and explain most of what is here:

- **One accent hue.** A coloured thing on a page therefore means something
  rather than decorating it. The eye goes to the state badge, which is the one
  thing on most pages that matters.
- **A hairline and a soft shadow together.** Every surface rests on a faint
  two-stop shadow: a tight stop for the edge, a wide one for the ambient fall,
  which is what light actually does. One stop reads as a smudge. They are kept
  deliberately faint, because the interface is dense tables and a heavy shadow
  under each one turns a page into a pile.

### Colour system

**Neutral ramp**, slate rather than pure grey, so white surfaces read warm
against it rather than clinical.

| Token | Light | Use |
|---|---|---|
| `--n-0` | `#ffffff` | surfaces |
| `--n-25` | `#f4f6fa` | page canvas, table heads |
| `--n-100` | `#e3e7ec` | hairlines |
| `--n-200` | `#cbd2db` | input borders |
| `--n-400` | `#8b96a5` | faint text |
| `--n-600` | `#5a6574` | secondary text |
| `--n-900` | `#10161f` | body text |

**Brand**, one hue.

| Token | Light | Dark |
|---|---|---|
| `--brand-500` / `--accent` | `#1d4ed8` | `#8ab0ff` |
| `--brand-600` / `--accent-hover` | `#1a3fae` | `#a6c2ff` |
| `--brand-50` / `--accent-tint` | `#eef3fe` | `#1a2436` |
| `--brand-100` / `--accent-soft` | `#dbe5fd` | `#22304a` |

The one gradient in the system, `--brand-gradient`, runs from `#2563eb` to
`#4338ca` and is used only on the brand mark. The dashboard hero uses
`--hero-wash`, a fade from the accent tint to the surface.

**Semantic.** Darkened from the Bootstrap defaults, which sit at exactly
**4.50:1** with white text and leave no margin at all.

| Meaning | Light | Was | Dark |
|---|---|---|---|
| success | `#146c43` | `#198754` | `#4ade80` |
| danger | `#b02a37` | `#dc3545` | `#f87171` |
| warning | `#ffc107` on dark text | unchanged | `#fbbf24` |

### Measured contrast

Computed with WCAG relative luminance. The requirement is 4.5:1 for normal text.

**Light theme**

| Pair | Ratio |
|---|---|
| body text on surface | **18.16:1** |
| body text on canvas | **16.78:1** |
| secondary text on surface | **5.92:1** |
| secondary text on canvas | **5.47:1** |
| link on surface | **6.70:1** |
| accent on its own tint (active nav link, eyebrow, administrator chip) | **6.03:1** |
| success text on its tint (instructor chip) | **5.70:1** |
| white on the primary button | **6.70:1** |
| white on success | **6.45:1** |
| white on danger | **6.50:1** |
| dark text on warning | **11.14:1** |

**Dark theme**

| Pair | Ratio |
|---|---|
| body text on surface | **13.87:1** |
| body text on canvas | **15.32:1** |
| secondary text on surface | **6.85:1** |
| link on surface | **7.77:1** |
| accent on its own tint | **7.21:1** |
| success text on its tint | **8.88:1** |
| dark text on the primary button | **8.58:1** |
| dark text on success | **10.42:1** |
| dark text on danger | **6.56:1** |

**Lowest text pair in either theme: 5.47:1**, against a 4.5:1 requirement.

Icons that sit in a tinted square beside a figure (`.stat-icon`) are graphics
and are held to 3:1: the lowest, the warning hourglass in light mode, is
4.35:1. The small icon beside a section title is decorative, hidden from
assistive technology, and drawn in the faint text colour (2.77:1); it carries
no information that the heading beside it does not already say.

### Typography

One family, **Inter**, self-hosted as two variable `woff2` files (Latin and
Latin Extended, about 120KB together), so every weight comes from one download
and the interface looks the same on every machine. The system stack follows it
as the fallback, and `font-display: swap` shows text immediately while the file
loads. Nothing is fetched from outside the platform.
Scale is a 1.125 ratio from a 15.6px base. The steps are small deliberately:
this interface is dense tables and short labels, not a magazine.

| Token | Size |
|---|---|
| `--text-xs` | 12px |
| `--text-sm` | 13.2px |
| `--text-base` | 15.6px |
| `--text-lg` | 17.2px |
| `--text-xl` | 20px |
| `--text-2xl` | 24px |
| `--text-3xl` | 30px |
| `--text-4xl` | 36px |

Weights 400 / 500 / 600 / 700. Line height 1.6 for body, 1.25 for headings.

### Spacing

4px base. Every margin and padding in the stylesheet is one of these, so
vertical rhythm is a consequence rather than an effort.

`4 · 8 · 12 · 16 · 20 · 24 · 32 · 48 · 64`

### Radius and elevation

`--radius-sm` 8px · `--radius` 12px · `--radius-lg` 16px · `--radius-pill` 32px

Three shadows, all layered, all used. `--shadow-sm` is the resting state of
every panel, card, alert and the sticky header. `--shadow-lg` is the hover of a
card that **leads somewhere**, selected by `:has(.stretched-link)` and paired
with three pixels of lift, and the resting state of the sign-in card. A card
that cannot be clicked has no business suggesting it can.

On dark the near stop carries most of the separation, because a wide soft
shadow disappears against a dark ground.

---

## Component library

### Base components

| Component | Class | States |
|---|---|---|
| Primary button | `.btn-primary` | default, hover with shadow, active, disabled at 55% |
| Secondary button | `.btn-outline-secondary` | default, hover, active, disabled |
| Destructive button | `.btn-outline-danger` | outlined until hover, then filled |
| Text input, select | `.form-control`, `.form-select` | default, focus ring, disabled, placeholder |
| Choice row | `.pick` | default, hover, checked, focus |
| Card | `.card` | static, or lifting when it wraps a link |
| Panel | `.panel`, `.panel-head`, `.panel-body` | container for tables and forms |
| Table | `.table-hover` | head, row hover, last-row borderless |
| Badge | `.badge`, `.text-bg-*` | seven semantic fills, both themes |
| Empty state | `.nothing` | one treatment everywhere |
| Breadcrumb | `.crumb` | default, hover |
| Side navigation | `.side-nav`, `.step-no` | default, hover, active with an accent bar and a filled step number |
| Header link | `.app-header .nav-link` | default, hover, active (the current area) |
| Avatar | `.avatar` | the account's initials in a circle |
| Page label | `.eyebrow` | small uppercase label above a heading |
| Hero | `.hero`, `.hero-mark`, `.hero-actions` | the top of each dashboard |
| Summary figure | `.stat`, `.stat-icon`, `.stat-value`, `.stat-label` | four icon tints: accent, ok, warn, bad |
| Section title | `.section-title` | heading with a quiet icon |
| Module card | `.module-card`, `.card-foot`, `.card-go` | cover, three-line summary, state and link at the foot |
| Module cover | `.module-art`, `.module-art-{colour}` | eight two-tone gradients with a dot grid, or an uploaded picture |
| Test terms | `.facts`, `.fact` | four tiles: questions, time limit, attempts, pass mark |
| Role chip | `.role-chip`, `.role-{role}` | administrator, instructor, trainee |
| Sign-in card | `.auth-card`, `.auth-icon` | on pages seen before signing in (`body.is-public`) |
| Reading progress | `.progress`, `.reading-progress` | page position within a module |

### Component states

**Interactive.** Every control defines default, hover, active and disabled.
Focus is defined **once**, globally, on `:focus-visible`, so no component can
be missed and none can disagree with another.

**Empty.** `.nothing` is the single treatment: an icon in a tinted circle, and a sentence saying
what the situation is. Somebody with nothing to do should be told that, rather
than left looking at a blank panel wondering whether the page failed to load.

**Error.** Server-rendered into the `.alert` block in `base.html`, tinted from
the semantic ramp so it reads in both themes.

**Loading.** Deliberately minimal. The platform is server-rendered and answers in
milliseconds. Two things happen in place: saving one test answer, which reports
itself next to the question, and asking the study assistant, which shows a
waiting line through htmx's indicator until the answer arrives. Skeleton screens
for pages that never take long would be decoration.

---

## Responsive design

Mobile first. Bootstrap's grid and breakpoints, with the container capped at
1240px above 1400px so long table rows do not stretch across a wide monitor.

| Band | Behaviour |
|---|---|
| under 576px | tighter padding, smaller headings, drawer navigation; the three summary figures stay side by side with the icon above the number |
| 576 to 992px | drawer navigation, single-column forms |
| 992px and up | bar navigation, persistent module sidebar, multi-column |
| **1200px and up** | **root 106.25%**, so the whole interface is proportionally larger |
| 1400px and up | container capped at 1240px |
| **1600px and up** | **root 109.375%** |

The size step is a root percentage, not a font size: every length in the
stylesheet is in rem, so type, spacing, radii and tap targets grow together
instead of a larger font sitting in unchanged padding. A percentage rather than
pixels keeps a reader's own browser font preference, which a px root would
overrule. The threshold is 1200px so a tablet in landscape stays where it was.

**One rule outranks the rest: nothing may push the page sideways.** Wide
content, which here means every table, scrolls inside its own
`.table-responsive` box. No automated test checks this; it was checked in a
headless browser at phone width.

---

## Accessibility

### Met, and how it was checked

| Requirement | Status |
|---|---|
| 4.5:1 contrast for normal text | **measured**, lowest pair 5.47:1 |
| 3:1 for meaningful graphics | **measured** on the summary icons, lowest 4.35:1 |
| 3:1 for large text | met by consequence |
| Visible focus indicator | one global `:focus-visible` rule, 2px accent, 2px offset |
| Touch targets | `--tap: 44px` minimum on standard buttons, inputs, nav links, choice rows; `.btn-sm` is 36px |
| Colour never carries meaning alone | every state badge carries its word: Passed, Failed, Due, Overdue, Not started, In progress, No test |
| Reduced motion | `prefers-reduced-motion` collapses all transitions; nothing animated here carries meaning |
| Text scaling | every size in `rem`, no fixed-height text container |
| Dark mode | follows the operating system, both themes measured |
| Semantic markup | real `table`, `th scope`, `label for`, `fieldset`/`legend`, one `h1` per page |

### Deliberately not claimed

**Keyboard navigation.** The brief lists it under WCAG AA. Keyboard-navigation
requirements were removed from this project at the owner's direction, so the
platform makes no claim to that part of AA and no requirement here depends on
it. Focus styling is still present, because it costs nothing and helps anybody
whose pointer is imprecise, but it is styling rather than a claim.

---

## Developer handoff

### How to use it

Reference **roles**, never ramps. A component that reaches for `--n-600`
instead of `--ink-soft` will look wrong in dark mode, because the dark theme
redefines the role block and leaves the ramps alone.

```css
/* wrong: survives one theme */
color: #5a6574;
color: var(--n-600);

/* right: survives both */
color: var(--ink-soft);
```

### Adding a page

1. `{% extends "base.html" %}` and a `{% block title %}`.
2. Open with `.page-head`, containing a `.crumb` if the page has a parent,
   then one `h1.h3`, then an optional `.lead-sm`.
3. Put tables and forms inside a `.panel`. Put summaries inside a `.card`.
4. Give every list an empty branch using `.nothing`.
5. Add no colour, spacing or radius of your own. If a token is missing, add the
   token.

### Theming

`data-bs-theme` is set on `<html>` before the stylesheets load, from
`prefers-color-scheme`, by a short script in `base.html`. It is set first on
purpose: applying it after the stylesheets shows a white flash to anybody using
dark mode.

### Performance

- Three local stylesheets (Bootstrap, Bootstrap Icons, `app.css`) and three
  local font files. No CDN: every asset is served by nginx from the platform
  itself, so the interface works on a machine with no outbound access.
- The Latin Inter file is preloaded from `base.html`; the icon font is about
  130KB and loads once, then comes from the browser cache.
- The brand mark is a shield icon on a CSS gradient, not an image file.
- No JavaScript beyond Bootstrap's bundle, htmx, `localtime.js`, and the short
  theme script.
- `app.css` is about 44KB uncompressed, most of it comments.

---

**Design system date**: 2026-10-12
**Verification**: 645 tests pass. The dashboards, module and reading pages,
test page, accounts list and sign-in pages were checked in a headless browser
at desktop and phone width, in light and dark.
