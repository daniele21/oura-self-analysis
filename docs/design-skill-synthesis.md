# Design Skill Synthesis — Oura Insights

**Date:** 2026-11-02  
**Status:** curated and integrated as ORIGINAL project-level instructions (not vendored third-party skill bodies, executables or assets).  
**Scope:** local-only health metrics web application, vanilla JS + CSS + SVG.  
**Goal:** assemble the best transferable design-engineering practices from multiple widely used public agent skill projects, and reject landing-page or cloud-incompatible practices.

## Source provenance

| Original source / inspected file | Reviewed GitHub blob SHA (2026-11-02) | Transferable practice | What we deliberately reject |
|---|---|---|---|
| Anthropic [frontend-design](https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md) | \`a5333457c414d20d625f307df945842c0952ecc3\` | Subject-specific art direction, type/space hierarchy, real-content critique, resist cookie-cutter cards and eyebrow decoration | Full-bleed marketing hero or novelty that crowds out charts; no code/skill body copied |
| [Impeccable](https://github.com/pbakaus/impeccable) | README \`8f27aa965cb56ab578d637e53f0392ae4e2d06db\` | Brief-driven \`shape → critique → audit → distill → polish → harden\` passes; component-scoped review; rank blockers before polishing | Automatic installer/hooks/binaries; unreviewed downloads, AI "slop score" as release evidence, stylistic escalation that harms readability |
| [Taste Skill](https://github.com/Leonxlnx/taste-skill) | README \`8efa355f7d03ada51edccea568dccf26e628b511\` | Existing-screen audit first, non-template visual direction, three justified candidate directions, browser screenshot → critique → iteration | Random visual direction/scripts, forced strong motion, photography or landing-page-style visuals inside health charts |
| [UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | README \`074a2706ee60450eecabf2a1e8b777c345f5baf7\` | Design-system recommendation before coding; chart-type selection by question; industry-specific anti-patterns; typography/color/UX checklists | Bulk catalog ingestion, remote font import, style picker driving scientific representation, automatic Python/Node scripts |
| Vercel [web-design-guidelines](https://github.com/vercel-labs/agent-skills/blob/main/skills/web-design-guidelines/SKILL.md) | \`ceae92ab319216a68274168fba9b63b998b65997\` | File-specific rule audit: semantic HTML, keyboard/focus, typography, animation, interaction quality, feedback | Fetching a mutable remote rule URL implicitly during every PR/CI, treating rules as substitute for rendered testing |
| [mae616 usability-psychologist](https://github.com/mae616/design-skills/blob/main/skills/usability-psychologist/SKILL.md) | \`72803b248c80d590a2902e30ba30c52302a06cad\` | Cognitive load, recognition over recall, error prevention, no context loss on tab/period switch, user-task validation | Repeated clarification questions that block straightforward code improvements |
| [mae616 accessibility-engineer](https://github.com/mae616/design-skills/blob/main/skills/accessibility-engineer/SKILL.md) | \`295cace77fc3b72ba570d8cb71b07e2f13143b96\` | Native HTML controls and minimal ARIA; keyboard first; dynamic state/focus management and table alternatives | Icon-only interactions with unreliable ARIA shims, ARIA added merely for decoration |
| Anthropic [webapp-testing](https://github.com/anthropics/skills/blob/main/skills/webapp-testing/SKILL.md) | \`4726215301db64a0cc4d41fc3219c61f37a30f4a\` | Browser reconnaissance before interaction, role-oriented test locators, screenshots at several widths and console inspection | Using public cloud-browser tests on real personal medical records; installing/running unchecked helper scripts |

**Source selection criteria:** original repository authorship, technical fit, explainable heuristics, reproducibility, agent compatibility, dependence on external code/runtime, license and health-data privacy. Popularity is a discovery signal, **not** proof that a method improves usability or scientific validity. Repository SHA values above are inspected file **blob SHAs**, not release tags, commit IDs or vendored dependency pins.

### License and supply chain

- This document paraphrases generic workflows/ideas rather than copying upstream SKILL.md files, example code, assets, names or bundled proprietary materials.
- Upstream licenses differ; some Anthropic skills refer to separately defined license terms. Review specific upstream license *before* any future verbatim vendoring.
- No \`npx\`, \`curl | bash\`, plug-in installation, downloadable binaries, auto-hooks, remote font, web image or API connector is added in this synthesis.
- The repository-local skills work without network, Node packages or extra tools. External references are used for human review, not automatically executed.
- Real Oura records never enter external design services, screenshot sharing or hosted LLMs. Synthetic fixtures only.

## The merged method (design director)

### 0. Subject and user job

The first input is NOT a mood board; it is a user question: for example, "Is REM proportion actually changing, or only total sleep duration?" Establish the **specific fact, decision or comparison** that the screen must clarify and distinguish estimation vs inference.

### 1. Shape: multiple credible directions, one constraint-led choice

Draw **three targeted candidates**, all plausible for a calm observatory (not randomized themes):
- **A — Quiet Editorial:** maximal typography/white space and one prominent story chart;
- **B — Data Observatory:** precise modular chart/annotation rhythm, clear axis and provenance;
- **C — Comparative Lab:** A/B time-window overlay and explanation-first inspector.

Choose the winner by a written scorecard: correct data semantics (hard gate), user task clarity 25, comparison clarity 20, hierarchy 15, accessibility 15, consistency 10, mobile legibility 10, personality 5. Document why the two alternatives were rejected. These weights are editorial design heuristics, not experimentally established effect sizes.

### 2. Specify states and copy before pixels

For each changed chart/control produce a lightweight contract:
\`QUESTION / PRIMARY VISUAL / CONTEXT / INTERACTION / DEFAULT / KEYBOARD / MOBILE / EMPTY / SPARSE / STALE / ERROR / MEANING / LIMITATIONS\`.

Label actual A/B date windows, phase identity, units, n/N coverage and data freshness. Make the difference between "not enough evidence" and "no change" unambiguous.

### 3. Build from one semantic design system

Tokens, typography, consistent spacing and color semantics come before detail CSS. Reuse the existing CSS/vanilla SVG app. Avoid unrelated redesigns and nested decorative cards. Encode metric identity by hue and comparison by solid/dashed stroke, not color alone. Keep system font/local assets and static privacy.

### 4. Product-specific visual grammar

- Sleep: composition stacked, trend 7-day, A/B overlays as three phase small multiples; percent ratio uses qualified sleep-duration denominators.
- Recovery: two HR/HRV charts share elapsed X but preserve independent Y; show selected vs personal reference, gaps and n.
- Activity: D+1/2/3 are waking days, not exactly 24/48/72 hours; cohort sizes and overlapping workouts remain visible.
- Insights: evidence-based observations, sample coverage, limitations, no medical/causal claims.
- Responsive is not just shrinking: at 320/375 use one chart at a time with clear inline labels; at 1280 place context beside the hero only if it improves comparative reading.

### 5. Critique independently and rank findings

Two distinct passes:
- **Visual/editorial critique** (hierarchy, reading order, information density, distinctness, copy, interaction friction): record problems and evidence, distinguish subjective taste from objective failure.
- **Technical audit** (focus preservation, semantic HTML, contrast, overflow, color-only encoding, browser warnings, missing/stale, URL routing, responsiveness, privacy): actionable file+line findings.

Priority: P0 data leakage or misleading plot; P1 unusable core flow or missing keyboard/contrast; P2 confusing hierarchy/labels; P3 purely aesthetic polish.

### 6. Distill → polish → harden

First remove redundant presentation and reduce competing controls. Polish spacing, chart scales, labels and interaction feedback **only after** underlying interpretation is correct. Harden missing states, date boundaries, errors, keyboard selection and device widths.

### 7. Verify in real browser with synthetic-only data

Pass Python/unit + JS lint/syntax; then Playwright/axe with **synthetic fixtures** at 320, 375, 768, 1280 CSS px. Test screenshot, layout overflow, keyboard, table-equivalent, repeated interactions, initial/empty/stale/error and no network calls. Compare side-by-side with known synthetic baseline. Manual human visual review must sign off significant stylistic changes. Do not claim "visually verified" when browser automation is not run.

### 8. Release only after gates

Deploy a pinned SHA to the private Mac only after CI and visual gate. Check the local API contract without printing real physiological values. Maintain a rollback route.

## Conflict resolution — which source wins?

1. **Privacy and honest chart semantics always win** over any aesthetic or interaction advice.
2. **WCAG and real usability** override bold aesthetics, animations, color or decorative choices.
3. **Observed existing repo behavior** overrides generic library assumptions (e.g. no required React or shadcn rewrite).
4. **Application task** overrides landing page instincts: no testimonial/social-proof/hero photo in an Oura analysis tool.
5. **Synthetic browser evidence** overrides static design review or subjective quality scores.
6. **Product-specific \`oura-health-charts\`** overrides generic chart rules in a source pack.
7. When sources conflict and no evidence exists, document a reversible tradeoff and test both variants on synthetic data.

## How agents should use it

- For any significant design change start with \`.agents/skills/oura-design-director/SKILL.md\`.
- Hand off to \`oura-product-design\` for hierarchy and tokens.
- Hand off to \`oura-health-charts\` for metric and chart semantics.
- Hand off to \`oura-visual-qa\` for synthetic browser tests and release gate.
- The three specialized skills refer back to this document; avoid repeating detailed formulas in every file.
- Keep decisions in a brief \`docs/design-decisions/<feature>.md\` when implementing a screen. A template is provided by the design-director skill.

## Immediate Oura target

**Sonno** is the reference screen. Aim for answer-first:
1. Actual last valid night + selected 7/30/90 window + n/N completeness.
2. One clearly dominant sleep stage/trend chart; direct compare 7v7 or 30v30.
3. Matching A/B labels + single relative-day inspector.
4. Selected-night details and methods behind a disclosure.

Do not deploy a new visual treatment until the synthetic visual baseline and browser QA suite are operating.
