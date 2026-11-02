---
name: oura-product-design
description: Define, review and redesign the Oura Insights information architecture, visual direction, navigation, typography, spacing and mobile UX. Use for any dashboard screen, flow, layout, design system or user-visible copy change.
---

# Oura product design — calm, evidence-first health observatory

Read docs/design-system-v1.md and docs/ux-audit-2026-11-02.md before changing screens. Inspired by the design process in Anthropic's frontend-design skill and Vercel's Web Interface Guidelines, but tailored to this specific local health product.

## Workflow

1. State one primary user question per view (Oggi: how are things? Sonno: how is my sleep changing? Recupero: what changed in autonomic signals? Attivita: how do I compare post-activity days? Insight: what is supported by data?). Avoid mixing these primary goals.
2. Document the hierarchy in three levels: **orientation** (range, last sync, coverage) → **answer** (one hero trend or comparison) → **inspection** (selected night, breakdown, evidence, table).
3. Write a compact one-page visual brief: intended decision, chart grammar, content order, navigation action, mobile adaptation, all five loading/missing/sparse/stale/error states. Explain one concrete choice specific to Oura physiological data rather than generic dashboard templates.
4. Use named design tokens rather than raw ad hoc hex values. Use only one card level for major sections and reduce nested box-within-box framing. Labels and details may be inline, with generous chart space.
5. Run the content pass: wording says *estimated light/deep/REM*, min night HR is not resting HR mean, last valid night is not automatically today. Avoid moralized status colors ("bad sleep") and clickbait insights.
6. Define keyboard sequence, focus behavior, touch target, screen-reader text and 320/375/768/1280 widths before coding.
7. Produce a change spec: new/removed components, states, responsive variants, synthetic screenshot scenarios, tests and rollback.
8. Critique the design: can the user compare 7v7 in under 10 seconds? Is sample coverage obvious? Is there one unmistakable primary chart? Is the same interaction labelled consistently across views?

## Oura-specific decisions

- Default visual language: quiet dark surfaces, very clear information hierarchy, restrained accent colors. Don't imitate Oura's proprietary brand or communicate medical certification.
- Small multiples for HR/HRV and stage comparisons when a combined legend would be crowded. Equal Y scale within each A/B panel; separate units/scale across metrics.
- Show actual calendar boundaries for every comparison, not only "last 7 days". Detect stale sync.
- Analysis detail is not the landing view; surface only one or two justified observations.
- On mobile, prioritize chart, then a compact numeric summary and a single contextual drilldown. Avoid 5 simultaneous navigation levels.
- Choose typography with tabular numerals and accessible labels over tiny uppercase metadata or decorative typography.

## Outputs

- A design brief or delta in docs/, including user questions and before/after hierarchy.
- Updated design tokens/components/IA only after a review of existing UI.
- Synthetic visual proof or clear record that it remains unverified.

## External references (read/review; not vendored)

- Anthropic frontend-design: https://github.com/anthropics/skills/tree/main/skills/frontend-design
- Vercel Web Interface Guidelines: https://vercel.com/design/guidelines
- WAI-ARIA Authoring Practices: https://www.w3.org/WAI/ARIA/apg/

These are review references, not permission to install unknown scripts or fetch private records.

## Privacy gate

Only use synthetic fixtures and screenshots in UI reviews. Privacy is part of the design: never reveal live medical readings, private timestamps, Oura identifiers or credentials in external tools or CI artifacts. Always preserve the loopback-only service.


## Multi-source synthesis — apply during redesign

This skill is the *design execution* layer under `oura-design-director` (see `docs/design-skill-synthesis.md`). Combine **Anthropic subject-first art direction**, **Taste Skill's audit-before-redesign and visual alternatives**, **UI UX Pro Max's design-system-before-implementation**, **Impeccable's shape/distill/clarify/typographic polish** and **mae616 usability-psychologist's recognition-over-recall approach**.

- Before changing CSS, generate three viable directions for the specific Oura view: Quiet Editorial, Data Observatory, Comparative Lab. Vary hierarchy, spatial rhythm, chart prominence and density; do *not* merely rotate palettes.
- Apply the design-director weighted rubric and write a one-paragraph reason for the winner. Factual chart correctness and privacy are hard gates, not weighted preferences.
- Run a cognitive-load test: what is the user's single next action; how many choices are simultaneously visible; are period A/B and n/N recognizable without memory or navigating away?
- First **distill**: remove redundant full-height cards and duplicate comparisons. Then **typeset**: strengthen meaningful data labels, units, baselines and chart hierarchy. Only then consider visual accents.
- Preserve task context on rerenders: a phase toggle must not reset the period, selected date, keyboard focus or accessible output unexpectedly.
- Visually iterate on *synthetic screenshots*; record why a direction beats the previous state. Limit motion to communicating an actual change.
- Reject full-bleed photography, dramatic marketing gradients, arbitrary randomness and conversion-focused patterns: this is a private data-analysis app, not a landing page.

Consult `docs/design-skill-synthesis.md` for reviewed upstream links/blob SHAs; no remote skill code is automatically imported.
