#!/usr/bin/env python3
"""Playwright smoke and synthetic screenshot evidence for Sonno mobile-first."""
from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

WIDTHS = (320, 375, 768, 1280)


def run(base: str, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            for width in WIDTHS:
                page = browser.new_page(viewport={"width":width,"height":850},
                                        device_scale_factor=1,
                                        reduced_motion="reduce")
                problems=[]
                page.on("pageerror", lambda err: problems.append(str(err)))
                page.on("request", lambda req:
                        problems.append("external network request blocked: "+req.url)
                        if not req.url.startswith(base) else None)
                try:
                    page.goto(base+"/#/sleep",wait_until="networkidle",timeout=30000)
                    page.locator(".sleep-stage-hero").wait_for(timeout=20000)
                    title=page.get_by_role("heading",name="Come cambia il tuo sonno")
                    assert title.count()==1 and title.is_visible(), "Missing visible Sonno h1"
                    assert page.get_by_role("button",name="Confronta periodi").is_visible()
                    assert page.locator(".sleep-overlay-panel").count()==3, "Three stage mini-graphs required"
                    assert page.locator(".sleep-context-fact").count()==2
                    assert page.locator(".sleep-deeper-analysis").count()==1
                    assert not page.locator(".sleep-deeper-analysis").evaluate("(el)=>el.open")
                    assert page.locator(".sleep-overlay-line.reference").count()>0
                    assert page.locator(".sleep-overlay-line.recent").count()>0
                    assert page.locator(".sleep-overlay-periods").is_visible()
                    # Width assertions are evaluated after render; no browser network to external hosts.
                    width_report=page.evaluate("""() => ({
                         viewport:window.innerWidth,
                         document:document.documentElement.scrollWidth,
                         body:document.body.scrollWidth,
                         stage:document.querySelector('.sleep-stage-hero').getBoundingClientRect().width
                    })""")
                    assert width_report["document"] <= width+1, (
                        f"horizontal page scroll at {width}px: {width_report}")
                    page.screenshot(path=str(out/f"sonno-compare-{width}.png"),full_page=True)
                    # Switching modes must retain focus even after DOM replacement.
                    composition=page.get_by_role("button",name="Composizione")
                    composition.click()
                    active=page.evaluate("document.activeElement?.getAttribute('data-focus-key')")
                    assert active=="sleep-Visualizzazione-composition",f"focus lost: {active!r}"
                    assert page.locator(".sleep-phase-svg").count()==1
                    page.get_by_role("button",name="Trend 7 giorni").click()
                    assert page.locator(".sleep-phase-svg").count()==1
                    page.get_by_role("button",name="Confronta periodi").click()
                    assert page.locator(".sleep-overlay-panel").count()==3
                    page.get_by_role("button",name="Percentuale").click()
                    assert page.locator(".sleep-overlay-panel").count()==3
                    assert "%" in page.locator(".sleep-overlay-stats").first.inner_text()
                    page.get_by_role("button",name="Minuti").click()
                    # Open disclosures: controls remain operable.
                    page.get_by_text("Altre analisi del sonno",exact=True).click()
                    assert page.locator(".sleep-deeper-analysis").evaluate("(el)=>el.open")
                    if width==375:
                        page.locator(".sleep-overlay-period select").select_option("30v30")
                        needed=page.get_by_role("button",name="Apri 90 giorni per il confronto")
                        assert needed.is_visible()
                        needed.click()
                        page.locator(".sleep-overlay-panel").first.wait_for(timeout=25000)
                        assert page.locator(".sleep-overlay-panel").count()==3
                        assert page.get_by_text("30 giorni",exact=False).count()>0
                        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
                        page.screenshot(path=str(out/"sonno-30v30-375.png"),full_page=True)
                    assert not problems,f"Browser errors: {problems}"
                finally:
                    page.close()
        finally:
            browser.close()


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--base",default="http://127.0.0.1:8766")
    parser.add_argument("--output",default="visual-evidence/sonno")
    args=parser.parse_args()
    run(args.base,Path(args.output))
    print("SYNTHETIC Sonno mobile/desktop visual QA passed; no real Oura records accessed.")
