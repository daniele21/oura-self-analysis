# Recupero Observatory — mobile-first design decision

Date: 2026-11-02  
Branch: `feature/mobile-first-recovery-observatory-20261102`  
Work item: #5  
Status: implemented as a pilot; synthetic browser and screenshot release gates pending.

## Task and data contract
**Question in 10 seconds:** Is my recent HRV or minimum nightly HR different from my own previous baseline, and do I have enough observed nights to compare?

Existing read-only `/api/dashboard?days=7|30|90` supplies `period_comparisons.windows["7v28"].metrics`; this remains the numerical source for recent median, non-overlapping preceding 28-day median, difference, coverage and status. Only individual days inside the selected 7/30/90 view may be rendered as lines. No new API or formula.

HRV is in **ms**; minimum nightly HR in **bpm**, with separate chart scales. Missing nights remain gaps, not zeros or interpolation; insufficient data suppresses values and comparisons rather than displaying a falsely precise delta. The baseline is statistical, not a clinical target.

## Alternatives considered

| Direction | Hierarchy | Mobile strength | Weakness |
|---|---|---|---|
| Quiet Editorial | One headline signal, other collapsed | Calm, focused | Hides the independent HR signal |
| Data Observatory | Both signals, trends, associations and nocturnal detail all visible | All evidence immediately available | Repeats charts/cards, high scroll and cognitive load |
| **Comparative Lab (chosen)** | Two compact signal cards, baseline+trend within each, single-night drilldown, advanced comparisons in disclosure | Both metrics understandable side by side conceptually, one per row on mobile | Still requires some vertical scroll |

Chosen due to explicit comparison job, reuse of established backend and consistent Sonno information architecture. This is a design hypothesis, not user-study evidence.

## Information architecture
1. **Orient**: genuine latest eligible night and comparison as-of day, including stale dates (global stale alert preserved).
2. **Choose window**: 7/30/90 controls, keyboard focus retained on re-render.
3. **Understand**: two focused summary cards with 7-day recent median, separate 28-day baseline, delta, n/N and chronological observations within selected range.
4. **Inspect**: one selected night's preexisting sampled 30-minute HRV/HR endpoint with synchronized keyboard cursor and accessible tabular alternative; choice retains the wake date deep link.
5. **Analyze**: disclosure for 7v7/7v28/28v28 detailed comparison, persistence and four prespecified non-causal associations.

At 320/375: full-width stacked panels, modest 26–31px values, contained SVG axis labels and touchable range selectors. At 768: wider plots. At 1280: two signal panels side by side, detailed nocturnal section below. No redundant top-level enormous KPI grid.

## Visual/test contract
- Separate HRV mint and HR blue; dashed warm baseline is **not** an alternate health status.
- Chart SVG scales adapt to viewport; ticks and actual first/last dates are readable; tooltips are not required to access data (table details).
- A missing individual day is not connected to its neighbor; reference line may exist without a valid recent median if the UI explicitly says insufficient comparison.
- Focus survives night date selection and 7/30/90 re-render.
- Tests use isolated synthetic local SQLite on 127.0.0.1 and avoid Oura health records, logs, analytics or screenshots of real data.
- Before merge: Python tests, JS syntax, Playwright complete/empty/sparse tests (320/375/768/1280), screenshot visual inspection and accessibility review. User-study/VoiceOver checks remain separate.
- Deployment to the private Mac and real-data SQLite qualitative audit are separate steps requiring the Mac environment. No public deployment.

## Review notes / sign-off

Pending screenshot evidence from PR Actions. Verify actual legibility and first-screen content density on 375px, not only the green CI. Check tabular alternatives and advanced comparison selectors. Stop on any P0/P1 semantic, privacy, focus or overflow problem. No Mac deployment or live-data audit as part of this PR.
