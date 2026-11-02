---
name: oura-design-director
description: Orchestrate a multi-reference UX/UI redesign for Oura Insights: merge verified public agent design practices, select an art direction, coordinate product design and chart semantics, and require independent synthetic visual QA before release.
---

# Oura Design Director — curated multi-skill synthesis

This is the entry point for **substantial visual/UX work** on Oura Insights. Read these documents first, without performing any automatic network fetch or install:

- docs/design-skill-synthesis.md — reference matrix, reviewed upstream provenance, merged method, conflict policy.
- docs/design-system-v1.md — target tokens, IA, components and chart grammar.
- docs/ux-audit-2026-11-02.md — actual repo risks; source-code audit is not screenshot proof.
- docs/scientific-methods.md — avoid misleading Oura interpretations.

Route to the three specialist skills as needed:
- .agents/skills/oura-product-design/SKILL.md
- .agents/skills/oura-health-charts/SKILL.md
- .agents/skills/oura-visual-qa/SKILL.md

## Run the eight-pass design cycle

1. **Understand**: pick one domain view, identify user question and "10-second answer", list currently competing cards/charts. Differentiate facts from visual hypotheses.
2. **Explore**: create three Oura-plausible **design directions**: Quiet Editorial / Data Observatory / Comparative Lab. Each must be expressed in information hierarchy, typography, density, chart layout and mobile behavior, NOT just color palettes. No full-page photomontages or flashy landing-page patterns.
3. **Choose**: score these on accurate chart semantics (mandatory), task clarity 25, comparison clarity 20, hierarchy 15, a11y 15, consistency 10, mobile legibility 10, personality 5. Explain winning tradeoffs and preserve two alternatives in decision brief.
4. **Specify**: define screen content order, default interaction, loading/empty/sparse/stale/error, edge cases and 320/375/768/1280 responsive layout. Define navigable focus when the view re-renders.
5. **Implement**: route hierarchy to oura-product-design; chart meanings to oura-health-charts; token and component names to docs/design-system-v1.md; prefer small, reversible changes in existing vanilla CSS/JS/SVG.
6. **Critique**: two independent reviewers/passes: one checks intent/cognitive load, one checks engineering (focus, contrast, gaps, chart deception, perf, privacy). List findings P0–P3 with source file and scenario; do not blur subjective polish and release blockers.
7. **Distill and verify**: first remove redundant cards; then polish type/spacing/stroke and harden bad inputs. Route to oura-visual-qa for SYNTHETIC browser screenshots, keyboard/accessibility, no data leakage, 320/375/768/1280. Iterate on actual rendered evidence, not just prompts.
8. **Release**: only after offline tests and visual review pass. Deploy exact SHA through existing self-hosted private runner with no patient values/identifiers/logs.

## Reference techniques adapted, not copied

- **Anthropic frontend-design**: a subject-specific design point of view, not generic SaaS motifs.
- **Impeccable**: shape / critique / audit / distill / polish / harden, component-scoped reviews.
- **Taste Skill**: audit first, visual variations grounded in the content, screenshot-review loop. Do not run its random design or asset search scripts.
- **UI UX Pro Max**: design-system-first, choose chart and typography by domain, explicitly record rejected anti-patterns.
- **Vercel web-design-guidelines**: accessibility/interaction review with traceable code findings; no mutable auto-fetch during CI.
- **mae616 usability-psychologist**: cognitive-load and recognition-over-recall review, preserve context.
- **mae616 accessibility-engineer**: native HTML before ARIA, keyboard/focus and readable table equivalents.
- **Anthropic webapp-testing**: browser reconnaissance and role-based navigation in synthetic environment.

References, source blob SHAs, external licenses/limitations and transfer/rejection choices are recorded in docs/design-skill-synthesis.md. No third-party skill source/code or installer is embedded here.

## Design decision record (per screen)

Create \`docs/design-decisions/<feature-slug>.md\` following these sections:

1. User task and the one decision to make;
2. Baseline screenshot provenance (synthetic only) and source observations;
3. Three plausible visual directions with tradeoffs and winner;
4. Hierarchy diagram: orientation → hero answer → contextual comparison → details;
5. Components and tokens; color/shape/linetype semantics;
6. Data contract: unit, sample coverage, nulls, reference window, provenance, uncertainty;
7. Interactions and UX states with keyboard / mobile behavior;
8. Synthetic browser QA results, unverified scenarios and P0–P3 findings;
9. Sign-off/rollback, current SHA and whether Mac deploy happened.

## Non-negotiable constraints

Privacy first: all real health data remain on the user's Mac. Never run hosted screenshots on real data, send personal Oura records to an LLM, install remote skill executables without approval, widen the server beyond 127.0.0.1 or treat a missing HRV bin as 0.

Truth first: 7/30/90 refer to calendar windows, HRV/HR units remain separate, D+1 represents waking days, all A/B period medians preserve independent samples and matching x/y comparison basis. No diagnostic certainty or claims that more REM is inherently better.

Accessibility first: semantic controls, preserve focus across toggles, accessible charts and tables, keyboard and mobile readability, reduced motion and visible n/N.

**Stop condition**: if only Python/JS unit tests pass, mark visual review **not yet verified**. Do not deploy a redesigned UI until synthetic browser evidence is captured and reviewed.
