#!/usr/bin/env python3
"""Synthetic-only responsive UX QA of Recupero; never read real Oura data."""
from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

WIDTHS = (320, 375, 768, 1280)


def check(base: str, output: Path, scenario: str) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            for width in WIDTHS if scenario == "complete" else (320, 375, 768):
                page = browser.new_page(viewport={"width": width, "height": 850},
                                        reduced_motion="reduce", device_scale_factor=1)
                errors = []
                page.on("pageerror", lambda err: errors.append(str(err)))
                page.on("request", lambda req: errors.append("external request: " + req.url)
                        if not req.url.startswith(base) else None)
                try:
                    page.goto(base + "/#/recovery", wait_until="networkidle", timeout=30000)
                    page.get_by_role("heading", name="Come cambia il tuo recupero").wait_for()
                    assert page.get_by_role("heading", name="Come cambia il tuo recupero").is_visible()
                    if scenario == "empty":
                        assert page.locator(".empty-state").is_visible()
                        assert (page.get_by_text("Misurazioni cardiovascolari non disponibili").count()
                                or page.get_by_text("Dati non disponibili", exact=True).count())
                        assert page.locator(".recovery-signal").count() == 0
                    else:
                        assert page.locator(".recovery-signal").count() == 2
                        assert page.get_by_role("heading", name="Variabilità cardiaca").is_visible()
                        assert page.get_by_role("heading", name="Frequenza cardiaca minima notturna").is_visible()
                        assert "Copertura" in page.locator(".recovery-signal").first.inner_text()
                        assert page.locator(".recovery-deeper").count() == 1
                        assert not page.locator(".recovery-deeper").evaluate("(el) => el.open")
                        assert page.locator(".recovery-range-bar").is_visible()
                        assert page.locator("#cardio-night-select").count() == 1
                        if scenario == "complete":
                            assert page.locator(".recovery-timeline-svg").count() == 2
                            assert page.locator(".recovery-chart-baseline").count() == 2
                            assert page.locator(".recovery-data-table").count() == 2
                        else:
                            # Sparse records remain sparse: no invented physiological medians.
                            assert "—" in page.locator(".recovery-signals").inner_text()
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), (
                        f"horizontal page overflow at {width}px, scenario={scenario}")
                    if scenario == "complete":
                        axis_problems = page.evaluate("""() => {
                          const results = [];
                          document.querySelectorAll('.recovery-timeline-svg').forEach((svg, i) => {
                            const area = svg.getBoundingClientRect();
                            const scale = area.width / svg.viewBox.baseVal.width;
                            svg.querySelectorAll('.recovery-chart-label').forEach(label => {
                              const box = label.getBoundingClientRect();
                              const style = getComputedStyle(label);
                              const px = parseFloat(style.fontSize) * scale;
                              if (style.stroke !== 'none' && style.stroke !== 'rgba(0, 0, 0, 0)')
                                results.push({i, label:label.textContent, issue:'axis text stroked'});
                              if (box.left < area.left - 1 || box.right > area.right + 1)
                                results.push({i, label:label.textContent, issue:'label clipped'});
                              if (px < 11) results.push({i, label:label.textContent, issue:'small axis', px});
                            });
                          });
                          return results;
                        }""")
                        assert not axis_problems, f"unreadable axis at {width}px: {axis_problems}"
                    if width in (375, 1280):
                        page.screenshot(path=str(output / f"recupero-{scenario}-{width}.png"),
                                        full_page=True)
                    if scenario == "complete":
                        if width == 375:
                            details = page.locator(".recovery-data-table").first
                            details.locator("summary").click()
                            assert details.locator("table tbody tr").count() >= 7
                            night_picker = page.locator("#cardio-night-select")
                            night_picker.focus()  # model actual keyboard selection
                            night_picker.select_option(
                                page.locator("#cardio-night-select option").last.get_attribute("value"))
                            assert page.evaluate(
                                "document.activeElement?.getAttribute('data-focus-key')"
                            ) == "recovery-night-picker"
                            page.locator(".recovery-deeper-toggle").click()
                            assert page.locator(".recovery-deeper").evaluate("(el) => el.open")
                            page.locator(".period-controls select").first.select_option("7v7")
                            assert page.locator(".period-summary").count() >= 1
                        page.get_by_role("button", name="7 giorni").click()
                        assert page.locator(".recovery-signal").count() == 2
                        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
                    assert not errors, f"browser errors at {width}px: {errors}"
                finally:
                    page.close()
        finally:
            browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8766")
    parser.add_argument("--scenario", default="complete", choices=("complete", "sparse", "empty"))
    parser.add_argument("--output", default="visual-evidence/recupero")
    args = parser.parse_args()
    check(args.base, Path(args.output), args.scenario)
    print("SYNTHETIC Recupero responsive QA passed.")
