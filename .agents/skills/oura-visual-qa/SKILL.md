---
name: oura-visual-qa
description: Review and test an Oura Insights UX, frontend or chart change for responsive behavior, accessibility, privacy, missing data and regression. Use before frontend PR review, release or dashboard Mac deployment.
---

# Oura visual QA — synthetic evidence only

This skill is intentionally separate from the product-design skill: it is the independent quality/release gate. Read AGENTS.md and docs/design-system-v1.md.

## Safety prerequisites

- Browser/screenshots/test recordings MUST use deterministic **synthetic-only** health data. Do not point cloud browser, screenshot service, visual-regression bot or GitHub Actions UI test at a user's real localhost Mac instance.
- Test server should be isolated and mocked to return a fixed synthetic response shaped like /api/dashboard?days=7|30|90 and /api/v2/recovery/night.
- Disable external fonts, CDNs, tracking, telemetry and hosted visual-diff services; keep screenshot artifacts on CI only if they contain no real records, identifiers or precise personal dates.
- If browser/test dependencies are unavailable, run the offline suite and record browser visual QA as **not verified**, never "done".

## Test matrix

For EACH changed top-level view (Oggi, Sonno, Recupero, Attivita, Insight), check:

| Dimension | Required scenarios |
|---|---|
| Width | 320, 375, 768, 1280 CSS px; consider 1440+ |
| Content | no data, sparse, complete 7/30/90, stale sync, failure |
| Charts | filled, missing-middle, trailing-null, one available channel, long/short labels |
| Comparison | A/B full, one side insufficient, date ranges and n/N match, units and sign correct |
| Interaction | tabs, focus-visible, keyboard tab order, inputs, sliders, table, back/deep-link |
| Accessibility | form labels, names, table alternative, contrast, target sizing, reduced motion |
| Safety | no external requests, no personal values in console/URL/CI artifacts, no new endpoint |
| Layout | no horizontal page overflow, no hidden bottom-nav targets, no footer collision |

## Repeatable review steps

1. Before editing, record the current component contract, primary user question, DOM structure and screenshots (synthetic data only).
2. Use the documented visual language and component tokens. Build ONE coherent before/after screen, not a CSS change covering every page.
3. Execute unit tests: python -m unittest discover -s tests -v.
4. Execute JS syntax checks: node --check dashboard/app.js and node --check dashboard/sw.js.
5. Run static skill/design tests: python -m unittest tests.test_agent_design_contract -v (or discover if tests aren't packaged).
6. When Playwright is installed in an approved CI context, use Playwright's accessible locators and @axe-core/playwright. Screenshot synthetic fixtures at mobile and desktop; run visual diff with explicit reviewed baselines. Never add an auto-update-baseline step to the default PR workflow.
7. Test keyboard focus progression through the entire flow, including native <select>, slider and disclosure. Automated accessibility tests cannot replace manual keyboard checks.
8. Verify no regression in existing 7/30/90 API views, no raw Oura values in screenshots or logs, no new public listener, and PWA static-cache version when visual assets change.
9. Attach a brief QA report to the PR: screen, before/after, widths, cases passed, accessibility findings, evidence URLs, blockers. Say whether screenshots were performed; do not imply they were if only tests and code inspection ran.

## Suggested tools (review before installing)

- Playwright + @axe-core/playwright: https://playwright.dev/docs/accessibility-testing
- Vercel web-design-guidelines: https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines
- Vercel before-and-after: https://github.com/vercel-labs/before-and-after

No shell script from a third party should be fetched/executed automatically. Pin reviewed versions, use lockfiles and isolated synthetic fixture tests if these dependencies are later approved.

## Privacy gate

Treat screenshots, mock API payloads, videos and browser console logs as potential personal-data artifacts. Privacy review is a blocking release criterion: use only synthetic Oura data and never attach captures of the real Mac dashboard to public CI/PRs.


## Multi-source synthesis — independent review

Use the **Impeccable critique/audit/polish/harden separation**, **Vercel web-design-guidelines file-level review**, **mae616 accessibility-engineer's native HTML/minimal ARIA principle**, **mae616 usability-psychologist's task friction review** and **Anthropic webapp-testing's inspect-then-interact flow**. Avoid vendored executables and mutable remote instructions.

- **Critique**: inspect the visible user task, hierarchy, visual consistency, cognitive overload, redundant cards, date/period comprehension and confusing terminology. Write one independently reviewable P0–P3 list with concrete screenshot scenario.
- **Audit**: verify semantic HTML, meaningful button/select names, keyboard focus retained on rerender, screenreader state announcements, contrast, layout overflow, bottom-nav safe area, performance and no remote data requests.
- **Polish** only after correctness and UX are clear: spacing, typography, chart labels, animation restraint, clear affordances. **Harden** sparse/empty, stale sync, missing samples, bad date/period, low contrast and narrow viewport.
- Use Playwright on synthetic-only pages: first wait for the actual view, inspect DOM/roles, *then* interact with accessible locators. For charts inspect both SVG and data table, not screenshots alone.
- Produce a before/after **visual evidence grid** at 320, 375, 768 and 1280 CSS px, with notes for layout, clipping and focus. If browser QA cannot run, record "not visually verified" as a blocker to redesign release.
- Don't download or execute Impeccable hooks/binaries, Taste Skill scripts, external rule packs or hosted screenshot services as a consequence of reading these instructions.

See `docs/design-skill-synthesis.md` for source provenance, conflict rules and why generic design-score claims cannot replace evidence.
