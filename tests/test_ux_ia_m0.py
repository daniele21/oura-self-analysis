"""M0 UI information architecture contract. Synthetic/static tests only."""
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class NavParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parent=[]
        self.nav_tabs={"side-nav":[],"bottom-nav":[]}

    def handle_starttag(self, tag, attrs):
        values=dict(attrs)
        if tag=="nav":
            self.parent.append(values.get("class",""))
        elif tag=="button" and "data-tab" in values and self.parent:
            current=self.parent[-1]
            if current in self.nav_tabs:
                self.nav_tabs[current].append(values["data-tab"])

    def handle_endtag(self, tag):
        if tag=="nav" and self.parent:
            self.parent.pop()


class TestMobileInformationArchitecture(unittest.TestCase):
    def test_same_five_destinations_mobile_and_desktop(self):
        parser=NavParser()
        parser.feed((ROOT/"dashboard/index.html").read_text())
        expected=["today","sleep","recovery","insights","training"]
        self.assertEqual(parser.nav_tabs["side-nav"],expected)
        self.assertEqual(parser.nav_tabs["bottom-nav"],expected)
        for tabs in parser.nav_tabs.values():
            self.assertNotIn("trends",tabs)

    def test_recovery_entry_has_real_computations_and_no_fake_series(self):
        code=(ROOT/"dashboard/app.js").read_text()
        self.assertIn("function recoveryView(data)",code)
        self.assertIn("data.records.filter",code)
        self.assertIn("state.sleepDay=day",code)
        self.assertIn('selectTab("recovery")',code)
        self.assertIn("function syncRoute()",code)
        self.assertIn("function applyRoute()",code)
        self.assertIn("function cardioNightChart(profile,selectedComparison=null)",code)
        self.assertIn("async function loadCardioNightProfile(day,host)",code)
        self.assertIn("profilo HR/HRV della notte selezionata",code)
        self.assertIn("Non ci sono",code)
        self.assertNotIn("const SAMPLE_HRV=",code)

if __name__=="__main__":
    unittest.main()
