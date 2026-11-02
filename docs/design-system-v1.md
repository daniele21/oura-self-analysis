# Oura Insights — design system v1 / proposed direction

**Status:** approved as a working design brief for the next redesign workstream; NOT automatically reflected in the current CSS.  
**Design concept:** Personal Health Observatory — calm, precise, explanatory, private.

## Audience and job

A physically active person reviewing real personal Oura nights and workouts. The user should be able to answer within 10 seconds:
- What changed compared with the right baseline?
- Is this a single noisy night or a trend?
- Is the observation supported by enough nights?
- Where can I inspect the specific night or the evidence?

This is **not** a clinical dashboard, social wellness feed, Oura-branded clone or status-score gamification interface.

## Principles

1. **The chart is the hero, not the cards.** Larger chart canvas, fewer surrounding borders, one primary question per screen.
2. **Read the answer first; inspect the method second.** A concise descriptive summary above the trend, then hover/keyboard selection, then expandable table and methodology.
3. **One hierarchy throughout:** orientation (period + last sync + n/N) → result (primary metric/chart) → context (comparison) → drilldown (night/date) → explanation (evidence/limits).
4. **Avoid decorative information.** No all-caps eyebrow on every section, every second element in a box, or a repeated "AI insight" banner.
5. **Clear clinical restraint.** State "estimato" for phases, "notte selezionata" vs "ultima osservazione", and "associazione" vs "causa".
6. **Usable on phone without turning the site into a miniature desktop dashboard.** Each screen shows one dominant graphic and one secondary action at a time.
7. **Private by default.** No external fonts, hosted image assets, analytics, chart SDK calls or third-party JS.
8. **Contextual actions.** From a trend, selecting a day opens its existing detail with the same waking day in the route.

## Information architecture

Keep the current five primary sections to avoid unnecessary migration:

| Section | First question / first view | Secondary depth |
|---|---|---|
| Oggi | What happened in the latest measured night? | Selected signals, comparison to recent baseline, links to Sonno / Recupero |
| Sonno | How is sleep evolving over 7/30/90 days? | Stage composition, period overlays, selected-night breakdown, comparisons and completeness |
| Recupero | How are HRV and min nightly HR evolving vs personal reference? | Night-level HR/HRV aligned bins, prior-week overlays, associations and caveats |
| Attività | What does recovery look like after recorded activity? | D+1/2/3 curves, type/intensity subsets, overlapping workouts |
| Insight | What is the strongest supported observation worth attention? | Evidence, sample size, window, alternatives, confidence limitations, provenance |

**Proposed Sonno screen order:** (1) chosen range + last valid data date + coverage; (2) one-line factual takeaway; (3) main Sleep Stage/Duration chart with tabs Composizione / Trend / Confronta; (4) drilldown of selected waking-day; (5) "Perché è cambiato?" contextual comparison and expandable limitations. The existing generic period comparison should not compete as another full-height "hero" card above/beside the stage chart.

**Proposed Recupero order:** signals HRV+FC baseline summary; two coherent trend lines; selected night and intranight details; qualified associations (collapsed by default). Avoid making four correlation coefficients look like four independent diagnoses.

**Proposed mobile navigation:** keep bottom tabs; a single row of in-view subnav for Sonno tabs. Preserve a clear current selection, data freshness and keyboard focus when updating chart range.

## Visual foundations — token target

These are proposed tokens for staged adoption, not a mandate to replace everything at once:

| Role | Token proposal | Value / intent |
|---|---|---|
| Page background | bg | #101820 — deep slate, not pure black |
| Primary surface | surface | #18242F — distinction without heavy box shadows |
| Elevated/control surface | surface-raised | #22313C |
| Main text | text | #F3F7F8 |
| Secondary text | text-secondary | #B0C1CB |
| Quiet labels | text-muted | #9BAFB9 — still readable on surfaces |
| Focus/primary action | accent | #A6E7CD — calm desaturated jade |
| Sleep/light | phase-light | #8ED0E6 |
| Sleep/deep | phase-deep | #A59CF0 — chosen to distinguish from the previous dark violet |
| Sleep/REM | phase-rem | #F2B38D |
| Period A/B | chart-period-a / chart-period-b | SAME phase hue: solid stroke A, dashed B |
| Border | border-subtle | rgba(184,208,215,.17) |
| Warning (stale data) | warning | #F0C48C, always with text |
| Error | error | #F3A9A7, never used to call low REM "bad" |

Use **semantic** tokens for data series, layers, charts, interactive and statuses. Adopt progressively in CSS variables after screenshots/contrast checks. Keep compatibility mappings for existing --mint, --blue etc. Do not hardcode new colors in each new view.

### Typography

- System font stack preferred: already loaded locally; no Google Fonts.
- Primary page heading: 28–36px desktop, 25–30px phone; section 18–22px; body 14–16px; secondary 12–14px. Essential units/sample coverage should not default to 9–10px.
- Use tabular numerals for metrics, delta signs, dates and columns.
- Labels short, sentence case, not every header uppercase with large tracking.
- One numeric hierarchy: primary value, explanatory label, deltas/coverage as supporting text. Avoid giant decorative values without units.

### Spacing and surfaces

- Base space scale: 4, 8, 12, 16, 24, 32, 48 px; assign tokens, not one-off values.
- Top-level content max width 1120–1240px, chart-first grid. Reasonable line length in descriptions: 60–75 characters.
- Main section surfaces have soft borders and sparing radius; nested statistics can be borderless with a subtle vertical rule. Reduce successive identical rounded cards.
- Touch targets >=44x44 CSS px on phones; visible focus ring >=2px; input font >=16px on mobile to avoid Safari zoom.
- Respect bottom tab bar and env(safe-area-inset-bottom). Never let it cover a selected point, button or keyboard focus.

### Graph grammar

- Light/deep/REM use consistent phase hue everywhere.
- Single phase graph: solid = observed; softer/secondary line = rolling reference.
- Period overlay: A=solid, B=dashed; BOTH on the same Y scale for that metric. Three small-multiple phase graphs rather than six lines overlaid in one panel.
- Label axes with units; dates anchored to waking days; show first/last absolute date.
- Missing nights/bins are null and segments do not connect across them.
- Data inspector and accessible table are not optional.
- Change in minutes vs percentage points must be explicit. Show n/N near summary.
- If last sync is stale, show "ultimo dato del…" and never make the headline appear to describe "oggi".
- Do not invent a normal physiological range from generic wellness guidance.

## Components to standardize

**Controls:** RangePicker (7/30/90), PeriodCompareSelect, MetricSelector, UnitToggle (min/%), NightSelector, Disclosure.  
**Evidence:** MetricSummary, ChangeSummary, CoverageLabel, StaleDateLabel, LimitationFootnote, EvidenceDrawer.  
**Charts:** TimeSeriesChart, PhaseStackedChart, PhaseOverlaySmallMultiple, CardioIntranightChart, GapMarker, ChartInspector, DataTable.  
**Layouts:** PageHeader, InsightHero, ChartSection, InspectionPanel, DomainSubnav, MobileBottomNav.

Write small focused DOM/SVG helpers or ES modules as a migration; preserve existing API and CSP constraints (external scripts not allowed). A full React rewrite is not a prerequisite.

## Five mandatory visual states

- Loading: stable layout skeleton, no flashing random values.
- Empty: specifically no main sleep data and a sync suggestion.
- Sparse: visible valid points with insufficient-summary notice, never a scary red health status.
- Stale: "ultimo risveglio registrato…" and no implied freshness.
- Error: read-only recovery action and clear message that data were not changed.

## Proposed phase-by-phase proof

1. **P0 UX & test foundation:** agent skills + design system doc + synthetic browser QA harness proposal.
2. **P1 Visual foundations:** tokens/contrast, typography and layout shell on one screen; static before/after synthetic screenshots.
3. **P2 Sonno as reference implementation:** reorganize stage chart as hero, period compare small multiples, explicit n/N and selected-night detail.
4. **P3 Recupero/Attività:** reuse components, simplify signal hierarchy and long insight groups.
5. **P4 Insight/Oggi polish:** evidence-first cards and consistent navigation. Finish with full visual/a11y/functional regression matrix.

## Success criteria

- An unfamiliar user can find the main trend and compare 7v7 in <10 seconds in a moderated usability check (hypothesis, not already measured).
- Three stage graphs share a visual grammar, same metric scales for A/B, no lines crossing missing data.
- 320/375/768/1280 px no unintentional horizontal page scroll or clipped nav.
- Interactive elements keyboard operable, all charts have readable text and tables, no low-contrast essential labels.
- Synthetic browser screenshots and manual review completed before production deploy.
- No change to physiological calculations or local-only privacy constraints.

References: Anthropic frontend-design, Vercel Web Interface Guidelines, WAI-ARIA APG and WCAG 2.2. Links and skill-install research in docs/ux-redesign-roadmap.md.
