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
