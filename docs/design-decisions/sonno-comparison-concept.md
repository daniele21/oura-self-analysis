# Sonno — first design decision record (concept; not UI implementation)

**Date:** 2026-11-02  
**Owner:** Oura Design Director  
**Status:** a concept choice for a SYNTHETIC design iteration; NOT browser-tested, user-tested, implemented or deployed.

## Primary job

"Are my light/deep/REM trends changing, and how does the current 7- or 30-day period compare to the preceding equal-length period?"

The user already has working composition, rolling-7, 7v7 and 30v30 controls in Sonno. The design problem is making the answer discoverable without a long scroll or duplicated generic comparison areas.

## Observed code-baseline risks (not measured UX failures)

- Sonno view is assembled within a ~1.8K-line dashboard/app.js along with 4 other domains.
- A specific stage chart and a separate generic period-comparison area both compete for chart prominence.
- CSS layers show nested cards, frequent small (10–12px) labels and per-component phase color definitions.
- Current CI verifies unit/API/syntax, but no synthetic browser screenshot or keyboard proof for these choices.

## Three alternatives

### A. Quiet Editorial

One large phase chart, substantial negative space, small in-context values, discreet secondary tabs below. Excellent for a calm overview, but the A/B comparison may require additional navigation.

### B. Data Observatory

One wide sleep-stage overview plus aligned numerical table and contextual charts visible. Good for technical detail and simultaneous inspection, but risks cognitive overload on 375px phone.

### C. Comparative Lab — *provisionally recommended*

A single **hero stage panel** with tabbed Composition / Trend / Confronta. When comparing, show three aligned small multiples for light/deep/REM; recent A solid, prior B dashed, with dates and coverage next to the graph. Selected-day inspector opens matching night details. Method and generic secondary comparisons are folded below, not another competing hero.

**Why C for this task:** A/B comparison is the current user goal, and the existing engine already computes qualified non-overlapping periods. C can reuse existing chart semantics and improve discoverability by reorganizing, not modifying the statistical pipeline. This is a reasoned hypothesis, not the result of usability testing.

## Comparison matrix (qualitative hypotheses)

| Quality | Quiet Editorial | Data Observatory | Comparative Lab |
|---|---|---|---|
| Understand phase trend quickly | Strong | Strong | Strong |
| Compare A/B without switching screens | Medium | Strong | **Strong** |
| 375px mobile density | Strong | Risk | **Manageable** |
| Accurate n/N and method | Good if disclosed | Strong | **Strong** |
| Distinct but restrained visual character | Strong | Medium | **Strong** |
| Cost of migration from current CSS/JS | Medium | High | **Low-medium** |

**Hard gates for every direction:** no misleading same-metric Y scales, no missing=0, preserved privacy, keyboard focus and accessible data table. A direction that fails any gate is rejected, independent of visual taste.

## Information architecture of proposed Sonno

1. **Orientation:** "Ultima notte valida" (actual date), available span and n/N. Show stale status if today differs.
2. **Answer:** hero Stage Explorer with tabs \`Composizione / Trend 7g / Confronta periodi\`.
3. **Comparison:** when Confronta selected, A/B date windows + per-phase small multiples with one synchronized accessible inspector.
4. **Detail:** click or select a night to open actual-night data, retaining waking day.
5. **Explanation:** methods, criteria for valid stages and data table in disclosure. Generic period analysis becomes a subpanel rather than another competing hero.

## Component-level brief

- \`SleepHero\`: header, data date, 7/30/90 controls, n/N. Preserve meaning between window switch and comparison window.
- \`StageViewTabs\`: native button/tab semantics with \`aria-selected\` if genuine tabs, otherwise an accurately labeled segmented button group. Never ARIA theater.
- \`PhaseSmallMultiple\`: one chart per phase, shared Y within A/B of that phase, solid/dashed patterns; missing remains gap.
- \`PeriodContext\`: explicit recent/reference date windows, minutes and weighted %, Δ with correct unit pp.
- \`SelectedDayInspector\`: paired-day keyboard cursor, announces actual A/B dates and values, supports n/N and \`—\` for gaps.
- \`EvidenceDisclosure\`: readable method, sample exclusions and no clinical conclusions.

## Responsive and state contract

| State | Requirement |
|---|---|
| 1280+ | Hero chart occupies most content width, selected-day context optionally beside it |
| 768 | Chart full width; compact context below, controls not crushed into one row |
| 375/320 | One plot at a time vertically; no horizontal page overflow, selector targets >=44px |
| Loading | Stable layout; no arbitrary values |
| Empty | Explain no qualifying main sleep nights and how to sync |
| Sparse | Show valid points with n/N; hide insufficient medians/deltas, not whole graph |
| Stale | Report "ultimo risveglio del…" rather than "stanotte" |
| Error | Preserve last valid visible data when safe; retry is explicit and read-only |
| Keyboard | After view/tab/period toggle retain meaningful focus; inspect values without hover |
| Reduced motion | No required animation; user can read chart without motion |

## Synthetic visual review (PENDING)

Before implementation: obtain screenshots at 320, 375, 768, 1280 from **synthetic-only** browser fixture, then visually compare A/B/C variants. Validate accessibility and complete a task-focused walkthrough ("find and compare REM 7v7") with keyboard and pointer. Distinguish screenshot proof from actual user research; neither has been done yet.

## Next implementation step

Build synthetic browser-test harness, then modify **only Sonno** using option C as an initial design hypothesis. Review before moving new layout tokens or components to Recupero and Attività. No changes to private Mac deploy at this design-planning stage.

Reference synthesis: docs/design-skill-synthesis.md.
