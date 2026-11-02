# Sonno Observatory — mobile-first pilot implementation

**Date:** 2026-11-02  
**Branch:** \`feature/mobile-first-sleep-observatory-20261102\`  
**PR:** https://github.com/daniele21/oura-self-analysis/pull/4  
**Status:** implemented as a reviewable pilot, protected by synthetic-only browser QA. Production Mac deploy is NOT part of this branch.

## UX decision applied

The **Comparative Lab** direction from \`sonno-comparison-concept.md\` is implemented as a single discoverable **Sonno hero**: actual last valid sleep date + sample completeness → period selector → estimated light/deep/REM composition, trend or A/B overlay → selected night → optional advanced analysis. Compared with the previous stacked-section design, this avoids placing the generic period-comparison chart and separate weekly analysis at the same visual level as the main stage comparison.

### Before → after hierarchy

| Previously | Mobile-first pilot |
|---|---|
| Large repeated app page header, period controls, multiple full-height sections | Compact screen-specific title, factual orientation and last-valid date |
| Stage chart one of several equal cards | One dominant stage explorer panel at top |
| Default phase composition even when user primarily wanted A/B | Default 7v7 overlay, still with composition and rolling trend one tap away |
| Generic comparison + weekly comparison always fully expanded | One labelled native disclosure "Altre analisi del sonno" |
| Date rail could expand body beyond 320px | Date rail scrolls within bounded grid cell |
| SVG axes designed for 720px then shrunk on phones | Responsive coordinate system for 320/375 and three-column desktop |
| Controls lose keyboard focus on \`render()\` | Focus restored to the same logical control by stable local focus key |

## Breakpoints: mobile FIRST, then expand

- **320–599 CSS px:** minimal title, two compact freshness/coverage facts, one full-width 7/30/90 row. Stage mode buttons use three equal touchable cells; units use two equal cells. Three phase mini-charts stack, and secondary details remain below a real disclosure. Keep ≥44px target sizes.
- **600–999:** chart full width with more breathing room; controls wrap horizontally; 640-wide synthetic SVG coordinate plane to retain axis typography.
- **1000+:** the three phase comparisons form a 3-column grid while each one retains an appropriately compact 360-wide coordinate plane; desktop details can use two columns.
- **Accessibility:** one visible Sonno h1; chart names and table equivalents remain; input changes retain focus; select native; cursors keyboard accessible; no required animation; reduced-motion CSS.

## Privacy and statistics unchanged

No updates to raw Oura reads, sleep-stage estimators, HRV/HR, numeric ranges, API scopes, data retention, network capabilities or service listening interface. Existing n/N gate and 7v7/30v30 sources are preserved. The browser screenshot harness uses a disposable synthetic SQLite file and runs only on 127.0.0.1 in an isolated GitHub runner. It never connects to the actual Mac or user data.

## QA stages and evidence

- Python unit suite and Node JavaScript syntax checks: GitHub PR 4, see associated \`Python tests\` action.
- Playwright with pinned \`playwright==1.56.0\` and a local Chromium copy:
  - full synthetic Sonno data 320/375/768/1280;
  - screen initial 7v7 and period switch to 30v30;
  - composition and rolling trend toggles + unit toggles;
  - focus preserved after DOM rebuild;
  - no document horizontal overflow;
  - sparse and empty/unavailable API states;
  - keyboard-accessible disclosure and phase data tables;
  - network requests remain local.
- Screenshots: uploaded as short-retention **synthetic-sonno-responsive** artifact to PR's Synthetic Visual QA run. These are fictional measurements and safe to share. **Manual pixel-by-pixel visual assessment not yet performed**; Playwright passing is not equivalent to user approval of aesthetics.

### Defects discovered and fixed by browser QA

1. At 320px the original ~90-item night rail forced the whole page to ~1787px wide. Fixed by zero-min grid columns and a locally scrolling date rail.
2. Empty dataset can make analytics API unavailable: present a distinct sync/error state rather than a fake zero-night physiological reading.
3. On narrow panels a desktop-sized SVG produced very small plot-axis text. Coordinates are now responsive rather than merely scaling the desktop graphic.

## Next gates

1. Synthetic screenshots visual review at 375 and 1280; check typography, truncation, chart stroke distinction, content grouping and bottom nav.
2. User review of actual hierarchy and behavior in a synthetic preview or draft deploy if desired. Never upload a screenshot of the real Oura UI.
3. Only after accepted design + green CI, merge the PR and pin a new source SHA in the existing Mac private runner.
4. Subsequent phases can extract repeated chart controls and apply the same semantic tokens to Recupero, Attività and Insight without rewriting their analytics.

## Rejected shortcuts

No \`overflow-x:hidden\` hack masking focusable content; no remote design service or uploaded health data; no complete SPA framework replacement; no medical claims; no auto-approved visual snapshot baselines.
