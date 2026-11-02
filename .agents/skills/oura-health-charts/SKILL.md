---
name: oura-health-charts
description: Design, implement, or review Oura Insights charts for sleep stages, HR, HRV, training and period comparisons. Trigger for axis alignment, missing values, series, thresholds, sample coverage, chart labels or graph quality.
---

# Health-chart design: evidence without misleading visuals

Read docs/scientific-methods.md and docs/design-system-v1.md as needed. Align chart semantics with existing backend contracts in sleep_stage_trends.py, sleep_stage_overlays.py, cardio_night_profiles.py, cardio_night_comparisons.py and period_comparisons.py.

## Select a representation based on the question

- **How has one measure evolved?** Use a chronological trend with visible actual dates, unit, valid points and optional 7-calendar-day robust reference. Distinguish raw nightly values from smoothing.
- **What portion of sleep is estimated light/deep/REM?** Use stacked bars (same denominator) for composition; trend lines for changes. Three stage colors map consistently across pages.
- **Are two periods different?** Use small multiples: one panel per stage, both A/B lines at the SAME Y scale within that panel; A solid, B dashed. Relative day G1..GN only when explicitly aligned. Show A/B calendar dates, n/N, minutes vs percent and A−B in min or percentage points.
- **What happens within one night?** Use elapsed time from bedtime based on timezone-aware source timestamps. Missing bins are gaps, no fake line through a null segment. HR and HRV have different vertical units/scales; inspect together only by shared X.
- **How do workouts relate to waking-day recovery?** Use D+1/D+2/D+3 timelines with cohort sizes and overlapping workout limitations, not an implied causal dose-response graph.

## Non-negotiable data semantics

1. Only qualifying Oura main sleep sessions for sleep-phase graphs. Deep, REM, light sums and time-in-bed require separate definitions.
2. Missing is null, never zero, except a *truly observed* zero. Do not forward-fill or cosmetically interpolate absent nights.
3. Percentages: numerator/denominator explicit; weekly phase percentages are time-weighted by total observed sleep, not arithmetic averages of nightly percentages. Unit pp for differences between percentages.
4. A/B periods: non-overlapping calendar windows, same comparison basis, no duplicated nights. If source ranges not visible, show the explicit range-expansion action; never silently leak individual older nights.
5. Anchoring: latest valid waking-day main sleep may precede today. Display as-of date and stale synchronization state.
6. Every display of a delta includes A period, B period and valid sample n/N or a reachable clear quality explanation.
7. Show only descriptive relationships, never a medically validated score or causal inference inferred from a wearable chart.
8. Chart title and summary must stand alone without color: define phase, unit, window, denominator, what the stroke/area represents and what happens on missing days.
9. Conserve source values and processing provenance; a 30-minute bin median is not the absolute HR minimum.
10. Never send graph data or screenshots of real measurements to cloud code review, LLMs, analytics or CI.

## UX quality review

- Keyboard-operable range and date controls; SVG with an accessible name and a real table alternative for dense charts.
- Readable at 320/375/768/1280 widths. Keep meaningful text >=12px where feasible and interactive targets >=44px on mobile.
- Use chart colors only for metric identity and linetype for A/B: the comparison must remain legible in grayscale.
- The closest legend corresponds to the chart, and no y-axis unit is ambiguous.
- Partial coverage isn't disguised as high precision: do not overlabel noisy points.
- Show sample coverage when selected date/range changes; prevent stale label after user selects another period.
- Test 0/1/3/4 valid nights, missing middle, trailing gaps, DST crossing, old last sync, denominator drift, different period lengths and both positive/negative deltas.

## Done criteria

Document baseline fixture, the exact semantic question, proposed chart, states, test data, delta formula and limitations; test with synthetic Oura rows only. Ask another agent to critique the graphic's meaning before marking it visually complete.

## External references

- Vercel Web Interface Guidelines: https://vercel.com/design/guidelines
- W3C WCAG 2.2: https://www.w3.org/TR/WCAG22/
- Oura local methodology: docs/scientific-methods.md

## Privacy gate

Real health records never enter CI, remote screenshots, cloud code-review or AI models. Privacy-safe charts are tested only with deterministic synthetic measurements. Maintain loopback-only API access and do not widen date-level visibility silently.


## Multi-source synthesis — chart-first review pass

In addition to the current domain rules, borrow **UI UX Pro Max's chart-by-question selection**, **Vercel's readable UI and feedback heuristics**, **Impeccable's audit/harden stage** and **mae616's cognitive-load reduction**. These are constraints, not new scientific estimators.

- For every new graph record: question → source metric/provenance → encoding → unit/denominator → display window → comparison window → sample n/N → missing-state → table alternative.
- Before implementation, compare 2 plausible encodings (for example stacked bars vs three mini-trends for REM/light/deep). Reject representations that obscure change or suggest unsupported causal interpretation.
- If overlaid A/B data use the same phase and unit, **force matching y limits** within that small multiple. Two different phases may have different y limits if visibly labeled.
- For 7v7/30v30, distinguish relative day G1…GN from calendar date and explicitly show actual reference dates. Day gaps remain gaps, not zeros. Never show weighted percentage as an average of percentages.
- Distill legends, selectors and nested boxes around charts until an unfamiliar reader can identify A vs B without memorizing a color. Use solid vs dashed, labels and nearest accessible inspector.
- Audit dynamic focus and screenreader output after toggling the metric/unit/period and after asynchronous night-profile replacement.
- Re-evaluate empty and sparse views as first-class layouts, not just an error message underneath a blank SVG.
- For privacy, CI diagrams must be rendered only from fixed synthetic fixtures and never from the user's real Oura API.

This is specifically the *domain truth gate* of `oura-design-director`; aesthetic source skill advice cannot override it.
