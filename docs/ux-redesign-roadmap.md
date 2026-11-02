# Oura Insights — UX/UI redesign roadmap

Date: 2026-11-02  
Status: P0 design governance integrated. Actual visual redesign remains a separate change, gated by synthetic browser QA and privacy review.  
Product: Oura Insights, local SQLite + Python HTTP + vanilla JS/CSS PWA.

## Design thesis

"Observe → Compare → Understand." Use a calm, evidence-first personal health observatory, not a generic SaaS metrics wall. Differentiate **data**, **change** and **interpretation** visually and through progressive disclosure. No proprietary Oura asset cloning or implied medical certainty.

Inputs:
- docs/ux-audit-2026-11-02.md (code-based findings)
- docs/design-system-v1.md (visual direction and tokens)
- docs/scientific-methods.md (metric semantics)
- docs/sleep-stage-overlay-comparison-plan.md (new 7v7/30v30 feature)
- .agents/skills/oura-product-design/SKILL.md
- .agents/skills/oura-health-charts/SKILL.md
- .agents/skills/oura-visual-qa/SKILL.md

## Work packages and dependencies

| ID | Scope | Depends on | Parallel possible? | Acceptance / gate |
|---|---|---|---|---|
| UX-00 | Design audit + IA + token proposal + AGENTS.md + 3 project skills | None | complete | Repo files, CI validates SKILL.md format |
| UX-01 | Synthetic browser harness (one deterministic mock payload per API range; no real health data), keyboard journey, accessible locators, screenshots for 320/375/768/1280 | UX-00 | With UX-02 | Reproducible snapshots in PR, zero network telemetry/external patient data |
| UX-02 | Extract CSS tokens and reusable visual components: PageHeader, RangeControls, CoverageLabel, DataTable, ChartLegend | UX-00 | With UX-01 | No changed physiological results; colors/units consistent; visual baselines reviewed |
| UX-03 | Prototype redesigned **Sonno** screen: context > hero stage chart > compare periods > night > methods | UX-01 + UX-02 | Core critical path | Compare 7v7 in max 2 interactions; explicit valid n/N; 320/375 widths pass |
| UX-04 | Refactor chart primitives into focused modules (axis, path/gaps, legend, accessible cursor, shared date axis) | UX-02 + UX-03 | With UX-05 | Never join across nulls; A/B same scale; no regression in 7/30/90 and URL routing |
| UX-05 | Redesign **Recupero**: HRV+HR baseline hero, deeper night graphs, exploratory associations not default clutter | UX-02 + UX-03 | With UX-04 | No clinical claim; keyboard/drilldown works |
| UX-06 | Redesign **Attività** and **Insight** for readable cohorts/evidence; remove repeated full-height cards | UX-04 + UX-05 | Sequential after shared chart primitives | D+1/2/3 coverage clear, no implied causes; consistent visual language |
| UX-07 | **Oggi** contextual summary, five-tab navigation and desktop/mobile shell final polish | UX-03–06 | Final stage | Freshness, empty/stale/error, back/deep link, safe-area/focus and zero overflow |
| UX-08 | Full visual and accessibility review + private deploy | UX-01, UX-03–07 | Last | CI green, screenshots reviewed, no health data in logs, exact pin SHA deployed |

## PR strategy

- PR 1: Design governance and repo-local agent skills (no product UI changes). **Prepared in current work**.
- PR 2: Synthetic-only UI/browser tests and initial visual baselines, reviewed dependencies/lockfiles.
- PR 3: Shared tokens, accessible labels and safe migration of reusable controls.
- PR 4: Sonno proof-of-concept at mobile + desktop; confirm direction before extending.
- PR 5: Recupero and data-viz refactor.
- PR 6: Attività, Insight and Oggi.
- PR 7: cross-screen QA and pinned self-hosted release.

Avoid landing all UX work on main at once. In this repo direct main changes have historically been used; for larger visual refactors prefer reviewable feature branch + CI + PR.

## Specific experience hypotheses and measurements

1. **Find trend quickly**: a user can locate the stage evolution chart in Sonno with zero scrolling on a 1280px desktop and roughly one screen on a 375px mobile (measure, do not assume).
2. **Compare 7v7**: ≤2 taps from landing Sonno; both A/B date windows and coverage are directly visible, without reading methodology.
3. **Understand an unusual night**: click date/point and reach that night detail with same waking date preserved.
4. **Avoid false confidence**: partial data states explicitly say "3/7 nights" and hide invalid deltas; no green/red clinical badge for a phase duration.
5. **Access for all**: keyboard/VoiceOver check for tabs, metric switch, sliders and table. Automated axe alone insufficient.
6. **Re-render focus**: ensure the control remains focused and screenreader value announced when changing chart mode or unit.
7. **Chart legibility**: no 9–10px essential values on mobile, comparison panel A/B lines remain distinguishable in grayscale.
8. **Performance**: avoid loading full 90-day raw series on dashboard initial view. Preserve one-night private endpoint and 7/30/90 scopes.

## Agent Skill strategy and supply-chain safety

**Native, in repo now:**
- oura-product-design: design reasoning and hierarchy.
- oura-health-charts: graph semantics, uncertainty, missingness.
- oura-visual-qa: QA workflow and privacy of screenshots.

**Recommended external references for agents, not installed automatically:**
- Anthropic frontend-design: https://github.com/anthropics/skills/tree/main/skills/frontend-design
- Vercel web-design-guidelines: https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines
- NextLevelBuilder ui-ux-pro-max: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill

Example after checking licenses, source and CLI (NOT run during this planning work):

~~~bash
npx skills add vercel-labs/agent-skills --skill web-design-guidelines
npx skills add anthropics/skills --skill frontend-design
~~~

These can assist reviews when available to the user's chosen coding agent; they don't replace product-specific skills. Before installing, inspect every fetched script/lockfile and run in a controlled project environment. No automatic network or dependency installation in GitHub Actions; do not blindly clone huge community skill collections.

**Agent compatibility:** root AGENTS.md is persistent guidance for Codex; project skills live at .agents/skills/<name>/SKILL.md. Compatible clients can discover the metadata and open instructions on demand. Agents that don't support this path should be pointed to AGENTS.md explicitly rather than pretending they have auto-discovered skills.

## QA implementation plan

- Stage 1: zero-dependency Python tests validate local SKILL.md contract, AGENTS references and design docs; CI always runs.
- Stage 2: browser testing dependencies as dev-only, lockfile pinned and reviewed. Serve **synthetic** local fixture, not user's SQLite. Playwright browser workflow tests across mobile/desktop, @axe-core/playwright WCAG checks, smoke test no external requests.
- Stage 3: compare screenshots in reviewed PR artifacts, using non-sensitive fixtures. Test changed charts plus all existing screens for regression, no auto-approve of visual baseline changes.
- Stage 4: after code/visual review, CI green and Mac-private run of selected SHA. Never capture actual Oura screenshot in Actions.

## Open design choices and trade-offs (not blockers for PR 1)

- Light theme? Start with high-quality dark theme; light mode only after consistent semantic tokens and contrast verification.
- JS framework migration? Deferred. First extract helper modules and state contracts; determine benefit after maintainability measurements.
- Charting dependency? Deferred. Existing hand-written SVG is privacy-preserving and adequate once refactored; adopt external library only with a measured reason and reviewed bundle/dependencies.
- Figma? Helpful for design review and handoff if needed later, but not a prerequisite to produce a browser-tested, accessible working app.
- Exact chart aesthetic? Compare synthetic screenshots at 375 and 1280 widths with criteria above rather than choose by prompt-style alone.

## Release status

- AGENTS.md, three native SKILL.md files, docs/design-system-v1.md, UX audit and this roadmap are initial artifacts of the design refactor.
- No new health-data APIs or external services.
- The substantive layout redesign is **not yet delivered**. Do not describe it as deployed until dedicated browser QA and final self-hosted verification pass.
