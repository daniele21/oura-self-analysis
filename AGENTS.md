# Oura Self-Analysis — repository instructions for coding agents

This is a privacy-first, **local-only** Oura Ring analysis and web UI. The Mac mini holds the real health records. GitHub contains code, tests and synthetic fixtures only.

## Read first

- For visual design, IA, typography or UX: .agents/skills/oura-product-design/SKILL.md
- For charts, comparative views, sample coverage or health metrics: .agents/skills/oura-health-charts/SKILL.md
- Before approving or releasing ANY frontend change: .agents/skills/oura-visual-qa/SKILL.md
- Current design direction, tokens and component contract: docs/design-system-v1.md
- Current findings and work breakdown: docs/ux-audit-2026-11-02.md and docs/ux-redesign-roadmap.md
- Statistical methodology: docs/scientific-methods.md
- Actual sources: dashboard/index.html, dashboard/styles.css, dashboard/app.js, dashboard_server.py

These are repo-local Agent Skills following the agentskills.io SKILL.md convention. Read the relevant skill on demand, rather than treating all instructions as one long always-on prompt.

## Permanent product rules

1. **No health data leakage:** never log, screenshot, upload, cache remotely, commit, or pass real Oura values, identifiers, access tokens or private local URLs to AI/external services. CI screenshots MUST use explicitly generated synthetic fixtures only.
2. **Privacy remains loopback only:** dashboard_server.py binds to 127.0.0.1; no public server, Tailscale Funnel, analytics SDK, web font, CDN or network telemetry. Ask before introducing new dependencies or a different deployment model.
3. **Truth before polish:** retain distinctions among Oura scores, physiological signals, estimated sleep stages, sample completeness and descriptive associations. Do not invent values, interpolate missing gaps or label observational trends as causal/clinical.
4. **Progressive disclosure:** each domain screen starts with one meaningful takeaway and a primary chart. Secondary interpretations and advanced tables are reachable, but not all equally prominent.
5. **One visual language:** use centralized design tokens, consistent spacing, typography and chart semantics. Colors indicate metric identity; stroke/dash/labels indicate period comparison. Never use color alone to convey meaning.
6. **Accessibility:** support 320/375/768/1280+ CSS px layouts; keyboard navigation, visible focus, reduced motion, accessible input labels and usable chart tables. Touch controls should aim for >=44 CSS px.
7. **Mobile-first, readable:** avoid truncating labels, overflow, sticky controls hiding focus or 10px microcopy for meaningful metrics; show units, window and n/N coverage adjacent to comparisons.
8. **Avoid unbounded monolith growth:** dashboard/app.js is already large (~1,800 lines). New view logic should be isolated into focused helpers/modules as part of staged refactoring, not pasted into a giant render function. Avoid framework migration until justified by tests and a measured need.
9. **Reversible changes:** preserve existing 7/30/90 API contracts, routes, PWA cache/version behavior and older feature affordances. Break UI projects into small independent PRs.
10. **No fake testing claims:** Python/JS syntax checks do not establish visual correctness; a deploy smoke test proves service health, not UX. Visual verification is separate and required for a redesign.

## Required workflow for UI work

- Understand the user's job to be done and inspect actual current UI code.
- Choose page/flow hierarchy and map all states: normal, sparse, missing, stale, loading, failure.
- Document design decision and how the interaction performs on small mobile screens.
- Implement with no extra network calls or stored private measurements.
- Test with: python -m unittest discover -s tests -v ; node --check dashboard/app.js ; node --check dashboard/sw.js.
- For any layout/chart update, perform the synthetic visual QA checklist in .agents/skills/oura-visual-qa/SKILL.md. If browser automation is not available, disclose the missing verification rather than claiming the design is visually validated.
- Do not deploy to Mac mini until offline CI is green. Pin the exact source SHA in the existing private runner deployment request. Never print personal metrics in Actions logs.

## Code Review Rules

- Flag real-record leakage or external network/data transmission as release-blocking.
- Flag misleading graphs (different Y scales for overlaid periods; missing=0; unexplained n; percentages without denominator) as release-blocking.
- Flag inaccessible chart-only information or controls, unhandled stale states and interactive buttons without action.
- Flag repeated UI components with inconsistent dates/units/labels, excessive font-size microcopy and unverified mobile overflow.
- Point out missing synthetic screenshot evidence; don't confuse static assertion tests with browser/visual tests.

## Current system

Python stdlib analytics + SQLite and loopback-only HTTP API; vanilla JS, CSS, inline SVG, PWA. Real Oura data never leave the Mac. Historical views include Sleep, Recovery, Activity and explainable insights. Keep this architecture unless an explicit redesign proposal, migration plan and regression tests justify change.
