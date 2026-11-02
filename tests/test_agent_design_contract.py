"""Repository design governance: skills are discoverable and privacy constraints persist.

Offline and metadata-only; reads no user health data or private directories.
"""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
SKILLS=("oura-product-design","oura-health-charts","oura-visual-qa")


class TestAgentDesignContract(unittest.TestCase):
    def test_root_agents_md_references_real_project_skills(self):
        guidance=(ROOT/"AGENTS.md").read_text(encoding="utf-8")
        self.assertLess(len(guidance.encode("utf-8")),32_000)
        for name in SKILLS:
            rel=f".agents/skills/{name}/SKILL.md"
            self.assertIn(rel,guidance)
            self.assertTrue((ROOT/rel).is_file())
        self.assertIn("127.0.0.1",guidance)
        self.assertIn("synthetic",guidance.lower())
        self.assertIn("node --check dashboard/app.js",guidance)

    def test_project_skills_follow_agent_skills_frontmatter_spec(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                source=(ROOT/".agents"/"skills"/name/"SKILL.md").read_text(encoding="utf-8")
                self.assertTrue(source.startswith("---\n"))
                header,body=source[4:].split("\n---\n",1)
                fields={}
                for line in header.splitlines():
                    if ":" in line:
                        key,value=line.split(":",1)
                        fields[key.strip()]=value.strip()
                self.assertEqual(fields.get("name"),name)
                self.assertTrue(fields.get("description"))
                self.assertLessEqual(len(fields["description"]),1024)
                self.assertTrue(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*",name))
                self.assertLess(len(source.splitlines()),500)
                self.assertGreater(len(body),200)
                self.assertIn("privacy",body.lower())

    def test_source_grounded_design_docs_exist_and_have_acceptance_criteria(self):
        paths=("docs/design-system-v1.md","docs/ux-audit-2026-11-02.md",
               "docs/ux-redesign-roadmap.md")
        for path in paths:
            with self.subTest(file=path):
                self.assertTrue((ROOT/path).is_file())
        roadmap=(ROOT/paths[-1]).read_text(encoding="utf-8")
        for item in ("UX-00","UX-01","UX-03","UX-08","Playwright",
                     "375","1280","synthetic"):
            self.assertIn(item,roadmap)
        design=(ROOT/paths[0]).read_text(encoding="utf-8")
        for item in ("Sonno","Recupero","Attività","Oggi","Insight",
                     "REM","CoverageLabel","touch"):
            self.assertIn(item,design)

    def test_skills_do_not_contain_hidden_executables_or_health_fixtures(self):
        root=ROOT/".agents"/"skills"
        for folder in root.iterdir():
            if folder.is_dir():
                self.assertIn(folder.name,SKILLS)
                self.assertEqual({x.name for x in folder.iterdir()},{"SKILL.md"})


if __name__=="__main__":
    unittest.main()
