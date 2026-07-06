# Open Steward — Design System

Open Steward's UI is a **black/white industrial monitoring console** with a single
neon-green accent. The goal is for it to read like a serious operational
data-platform tool — an instrument for watching pipelines — rather than a generic
SaaS dashboard.

The visual direction is inspired by real-time monitoring consoles: a strong left
command sidebar, a top system/status bar, dense framed instrument panels, sharp
technical typography, and neon accents used sparingly to call out live/healthy
state. Inspiration only — none of the reference's product name, labels, logo, or
layout are reproduced.

---

## 1. Design language

| Principle | What it means here |
|---|---|
| **True black, high contrast** | Near-black surfaces (`#0a0a0a`), near-white text. Contrast does the work; color is rationed. |
| **Framed instruments** | Content lives in bordered panels with a header strip — like gauges on a console, not floating cards. |
| **Sharp corners** | Small radius (`0.25rem`). Crisp, rectangular, technical — not pill-soft. |
| **Mono technical type** | Values, ids, table names, timers and meta use a monospace font with `tabular-nums`. Labels are uppercase, wide-tracked "eyebrows". |
| **Neon used sparingly** | Green marks live / healthy / active state and the single headline status. It is never used as a background wash for whole pages. |
| **Inverted KPI cards** | The headline dashboard metrics are white cards with black text — a deliberate inversion that makes the numbers pop against the black shell. |
| **Density with hierarchy** | Lots of information, but a clear order: eyebrow → title → value → meta. |

---

## 2. Color tokens (dark theme — primary)

Defined as HSL CSS variables in `src/index.css` (the app always runs `.dark`).

| Token | Value | Use |
|---|---|---|
| `--background` | `0 0% 4%` | Near-true-black app background |
| `--foreground` | `0 0% 96%` | Primary text (also the "white" of inverted cards) |
| `--card` | `0 0% 7.5%` | Panel / surface fill (one notch above black) |
| `--primary` | `142 84% 52%` | **Neon green** — live/healthy/active, accents, primary buttons |
| `--primary-foreground` | `0 0% 5%` | Text on green |
| `--muted` | `0 0% 13%` | Inset fills, disabled chips |
| `--muted-foreground` | `0 0% 62%` | Secondary text |
| `--accent` | `0 0% 14%` | Hover / active row background |
| `--destructive` | `0 84% 60%` | Errors |
| `--border` | `0 0% 18%` | Crisp neutral frame lines |
| `--input` | `0 0% 22%` | Input borders |
| `--ring` | `142 84% 52%` | Focus ring (green) |
| `--radius` | `0.25rem` | Global corner radius (sharp) |

The body adds a faint technical grid and a single restrained neon glow in the
top corner — structure comes from the panels, not from background color.

---

## 3. Status semantics

One consistent vocabulary across every page. Each status has a color, a `StatusDot`,
and (where relevant) a `Badge` variant.

| Status | Meaning | Color | Components |
|---|---|---|---|
| **healthy / active** | Connected, enabled, optimal, live | Neon green (`primary` / emerald) | `StatusDot status="healthy"`, `Badge variant="success"` |
| **warning** | Row loss, high null rate, attention needed | Amber | `StatusDot status="warning"`, `Badge variant="warning"` |
| **error** | Duplicate target, PK issue, unreachable backend | Red (`destructive`) | `StatusDot status="error"`, `Badge variant="error"`, `role="alert"` |
| **info** | Advisory / informational findings | Sky | `StatusDot status="info"`, `Badge variant="info"` |
| **idle** | Disabled / paused / not computed | Slate | `StatusDot status="idle"` |

`—` (em dash) always means *not computable* (missing table, no primary key,
empty-string stats on a non-text column) — never zero.

---

## 4. Typography

- **Eyebrow** (`.eyebrow`): 10px, uppercase, `0.2em` tracking, muted. Labels every panel and page section.
- **Techmeta** (`.techmeta`): mono 11px, uppercase, used for session/scope/engine meta, table names, timers.
- **Titles**: bold, uppercase, tight tracking for page `h1`s and the brand.
- **Values**: monospace + `tabular-nums`, large and bold for KPIs.
- **Body**: sans, `text-sm`, comfortable leading for messages and descriptions.

---

## 5. Core components

| Component | File | Role |
|---|---|---|
| `Panel` / `PanelHeader` / `PanelBody` | `components/ui/panel.tsx` | The framed instrument surface. Optional neon top accent rail (`accent="primary\|healthy\|warning\|error\|info"`). Header strip is slightly lifted and divided from the body. |
| `StatusDot` | `components/ui/status-dot.tsx` | Small semantic dot; `pulse` adds a soft ping for live/healthy. |
| `Badge` | `components/ui/badge.tsx` | Sharp rectangular mono status chip (`error/warning/info/success/muted/solid`). |
| `Card` | `components/ui/card.tsx` | Sharpened flat surface, kept for compatibility; new layouts prefer `Panel`. |
| `Button` | `components/ui/button.tsx` | Sharp-cornered; `default` is green, `outline`/`ghost` for secondary actions. |
| `Skeleton` | `components/ui/skeleton.tsx` | Pulsing placeholder shaped like the content it stands in for — every page loads with content-shaped skeletons, not a bare spinner. |
| `ErrorState` | `components/ui/error-state.tsx` | The one error surface: red-railed panel, `role="alert"` message, and a **Retry** button — no dead ends. |

### Motion

Small and consistent: panels rise in with `.panel-in` (280ms ease-out), KPI
numbers count up on the Overview (`useCountUp`, ~600ms), edge/node focus fades
at 150ms. All motion collapses to ~0ms under `prefers-reduced-motion` (and
count-up snaps instantly wherever `matchMedia` is unavailable), so screenshots
and accessibility both see final states.

---

## 6. Layout shell

- **Left command sidebar** (`AppShell`): brand block (square framed logo + `OPEN STEWARD` wordmark + `SYS · STEWARD.CORE` meta); primary nav where the **active item is inverted** (white box, black text) with a green status dot; a lower **System** panel showing engine status and version.
- **Top system bar**: a green `SYSTEM ACTIVE` pill, a `PIPELINE MONITORING` title, `ENGINE :: RECONCILE` meta, and a framed `Config` control on the right (mono input).
- **Main**: scrollable content region with consistent `p-6` padding and `space-y` rhythm.

---

## 7. Page archetypes

| Page | Archetype | Treatment |
|---|---|---|
| **Overview** | Command center | Row of KPI tiles — three **inverted white** tiles (count-up numbers) plus one **neon-green headline status** tile — then a **Signals** panel (error/warning/row-loss/PK counts linking to Findings and Statistics), a configured-jobs roster, a connection-status panel and an enabled-ratio meter. |
| **Findings** | Alert feed | Mono summary chips with status dots, severity filter buttons, then a single panel of dense alert rows with a colored severity rail, status dot, severity badge, mono finding type, and a `transform` tag for reconciliation findings. |
| **Statistics** | ETL telemetry | Summary instrument tiles, then one panel per job — header shows `config_key`, name, `source → target`, and row-loss / pk-issue badges; body is a grid of mono metric readouts. Panels gain a warning/error accent rail when flagged. |
| **Profile** | Data-quality inspection | A target-table control strip, table-level summary stats, a dense per-column table (nulls / distinct / empty), and a data-quality findings feed. |
| **Graph** | Topology view | React Flow canvas framed to match: sharp-cornered nodes with a colored namespace rail (source = green, staging = sky, mart = violet), edge labels hidden until hover/selection, **focus mode** (selecting a table dims everything unrelated; Esc clears), an edge/table inspector with a "Profile this table" jump, a collapsible execution-order rail, themed minimap/controls, and an eyebrow-labeled legend. |

---

## 8. Screenshot standards

The canonical screenshots live in [`screenshots/`](screenshots/) and document the
final control-room look. Standards for keeping them consistent:

- Capture against **`showcase_config.csv`** (the dataset that exercises every page).
- Use the **dark theme** (the app's default and only shipped theme).
- Capture at a desktop width (~1280px) so panels and the graph lanes are legible.
- Name files `<page>-<variant>-showcase.png` and reference them with **relative
  Markdown paths** and descriptive alt text.
- The graph should be captured at its clean default `fitView` (edge labels hidden);
  capture inspector variants with an edge or a table selected.

| File | View |
|---|---|
| `overview-showcase.png` | Overview command center |
| `graph-showcase.png` | Graph topology (default, labels hidden) |
| `graph-inspector-edge-showcase.png` | Graph — edge inspector |
| `graph-inspector-node-showcase.png` | Graph — table inspector |
| `findings-transformations-showcase.png` | Findings — reconciliation results |
| `findings-errors-showcase.png` | Findings — error-severity filter |
| `statistics-showcase.png` | ETL statistics telemetry |
| `profile-showcase.png` | Table profile |

---

## 9. Constraints honored

This is a **frontend-only** design system. No backend, API contract, showcase
data, or product-feature changes accompany it. No heavy dependencies were added —
styling is Tailwind utility classes plus the existing `lucide-react` icons and
`@xyflow/react` graph library.
