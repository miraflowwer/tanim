# TANIM Design System (universal-but-thin)

Single source of truth for `feat/mvp-ui` and future TANIM interfaces.
Plain CSS + variables only — no Tailwind, no component library.

## 1. Principles

1. **Farmer-first legibility.** 18px base, 48px+ touch targets, one idea per
   row. Must read on a phone in sunlight and on a pitch projector.
2. **Evidence honesty.** Every number carries its label: synthetic,
   historical, national, or committed local. Never upgrade weak evidence.
3. **No fake demand.** Only `local_committed_demand` may be called “market
   demand”. Historical production is a baseline; national utilization is
   context only.
4. **Range, not false precision.** Any value derived from an approximate farm
   size shows `Estimated range: X to Y` — never a single exact number.
5. **Display only.** The UI never computes GRCI math. `scripts/grci.py` owns
   all classification; the UI renders precomputed JSON.

## 2. Tokens (`src/styles.css`)

| Token | Value | Use |
|---|---|---|
| `--color-bg` | `#f6f4ec` | Page background |
| `--color-card` | `#ffffff` | Cards |
| `--color-ink` | `#1d2b1f` | Text |
| `--color-muted` | `#5c6b5e` | Hints, labels |
| `--color-border` | `#d9ddd2` | Card/field borders |
| `--color-primary` | `#2e7d32` | Primary button, links |
| `--color-low` | `#2e7d32` | Low state |
| `--color-watch` | `#8a5a00` | Watch / borderline |
| `--color-high` | `#b3261e` | High state |
| `--color-baseline` | `#1565c0` | Historical baseline |
| `--color-context` | `#616161` | Context / neutral |
| `--color-synthetic` | `#6a1b9a` | Synthetic badge |
| `--fs-base` | `18px` | Body |
| `--radius` | `12px` | Cards |
| `--max-width` | `720px` | Single-column measure |

Type: system stack only (no webfont download on pitch wifi).
Spacing: 0.25 / 0.5 / 0.75 / 1 / 1.5 / 2rem.
Layout: single column mobile-first; one breakpoint at 768px
(`.tanim-row-2` becomes 2 columns; header grows).

## 3. Copy rules (English-first, bilingual hints)

- UI chrome in English; key inputs carry Tagalog hints:
  `Crop / Pananim`, `Submit plan / Isumite`,
  `How unsure is the size? / Gaano kasigurado?`
- Full Tagalog translation is deferred; do not invent new Tagalog strings
  outside the approved hints above.
- Engine `explanation`, `reference_evidence_note`, `uncertainty_note` are
  rendered verbatim — never paraphrased.

## 4. Components (only 4)

### PlanForm
Seven inputs in fixed order: crop → Luzon region (direct select, no
geocoder) → municipality free text → farm size → ± margin → planting date →
harvest `YYYY-MM`. Client checks required + numeric ≥ 0 only.

### DemoPresets
Four buttons: `Tomato demo (high)`, `Eggplant demo (low)`,
`Baseline wording`, `National context`. Fill + fetch only.

### EvidenceBadge
Maps `reference_quality` → pill:
`SYNTHETIC` (purple), `HISTORICAL PROXY` / `HISTORICAL BASELINE` (blue),
`NATIONAL CONTEXT` (grey), `COMMITTED LOCAL` (green).
Always paired with `reference_label` + raw `reference_type` code.

### ResultCard
Fixed row order: state banner → planned area → estimated range (only when
low≠high) → reference yield + source → expected production → comparison
reference + demand guard → reference type + badge → evidence note →
GRCI/comparison state + supply load → uncertainty → explanation verbatim →
plan recap → `<details>` provenance.
State banner class: `tanim-state-{status}`; `ok` shows `risk_state`,
`baseline` shows `comparison_state` prefixed “Baseline comparison (not a
demand risk)”, `context_only` shows “Context only — no local comparison”.

## 5. Wording guards (must-pass)

- `market_demand_wording_allowed === false` → show
  “This reference must NOT be called market demand.”
- `historical_production_baseline` → never “demand”; `risk_state` must stay
  empty, only `comparison_state`.
- `national_utilization_context` → `supply_load_range` is null; show
  “not computed for this reference”.
- `demo_coordination_baseline` → always `SYNTHETIC` badge + full evidence
  note containing “not observed local market demand”.

## 6. What NOT to build yet

Municipality geocoder, charts, auth, multi-farmer aggregation UI, yield map,
price display. Those wait for backend + pilot evidence.
