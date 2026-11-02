"""Synthetic empty/sparse Sonno layout QA. No real health data."""
import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright


def run(base, scenario, out):
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        try:
            for width in (320,375,768):
                page=browser.new_page(viewport={"width":width,"height":850},
                                      device_scale_factor=1,reduced_motion="reduce")
                errors=[]
                page.on("pageerror",lambda exc: errors.append(str(exc)))
                try:
                    page.goto(base+"/#/sleep",wait_until="networkidle",timeout=30000)
                    page.get_by_role("heading",name="Come cambia il tuo sonno").wait_for()
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"),\
                        f"Overflow in {scenario} {width}"
                    if scenario=="empty":
                        # No data at all may make the analytics endpoint unavailable.
                        # This is an error/sync state, NEVER evidence of 0 minutes asleep.
                        assert page.locator(".sleep-dashboard .empty-state").is_visible()
                        assert page.get_by_text("Dati non disponibili",exact=True).is_visible()
                        assert page.locator(".sleep-context").count()==0
                        assert page.get_by_text("0 min",exact=True).count()==0
                    else:
                        assert page.locator(".sleep-stage-hero").is_visible()
                        assert page.locator(".sleep-overlay-panel").count()==3
                        assert "Confronto parziale" in page.locator(".sleep-phase-compare").inner_text()
                        assert "notti valide" in page.locator(".sleep-context").inner_text()
                    if width==375:
                        out.mkdir(parents=True,exist_ok=True)
                        page.screenshot(path=str(out/f"sonno-{scenario}-375.png"),full_page=True)
                    assert not errors,f"{scenario} browser errors: {errors}"
                finally:
                    page.close()
        finally:
            browser.close()


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--base",required=True)
    ap.add_argument("--scenario",required=True,choices=["empty","sparse"])
    ap.add_argument("--output",default="visual-evidence/sonno")
    args=ap.parse_args()
    run(args.base,args.scenario,Path(args.output))
    print(f"SYNTHETIC {args.scenario} Sonno visual QA passed.")
