"""The service-workflow templates stay blank, linked and complete."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"
TEMPLATES = SERVICES / "templates"
LINK = re.compile(r"\]\(([^)#]+\.md)(?:#[^)]*)?\)")
BLANK_NOTICE = "Never commit a filled-in copy."


class TemplateTests(unittest.TestCase):
    def test_every_template_is_listed_and_every_listed_template_exists(self):
        listed = {Path(p).name for p in LINK.findall((SERVICES / "README.md").read_text()) if p.startswith("templates/")}
        present = {p.name for p in TEMPLATES.glob("*.md")}
        self.assertEqual(listed, present)

    def test_relative_links_resolve(self):
        for doc in [SERVICES / "README.md", *TEMPLATES.glob("*.md")]:
            for target in LINK.findall(doc.read_text()):
                if target.startswith("http"):
                    continue
                with self.subTest(doc=doc.name, target=target):
                    self.assertTrue((doc.parent / target).resolve().is_file())

    def test_templates_ship_blank(self):
        for t in TEMPLATES.glob("*.md"):
            text = t.read_text()
            with self.subTest(template=t.name):
                self.assertNotRegex(text, r"\[[xX]\]", "a box is pre-ticked")
                if t.name != "case-study-gate.md":
                    self.assertIn(BLANK_NOTICE, text)

    def test_qa_outcome_rules_present(self):
        text = (TEMPLATES / "qa-signoff.md").read_text()
        for word in ("PASS", "FAIL", "INCOMPLETE", "BLOCKED", "Never mark PASS"):
            with self.subTest(word=word):
                self.assertIn(word, text)

    def test_completion_gate_covers_every_outcome_but_pass(self):
        # A test that couldn't be run must not let a job through when one that didn't finish can't.
        text = (TEMPLATES / "qa-signoff.md").read_text()
        gate = re.search(r"A job with any (.+?) item isn't handed over as complete", text, re.S)
        self.assertIsNotNone(gate, "completion gate missing")
        for outcome in ("FAIL", "INCOMPLETE", "BLOCKED"):
            with self.subTest(outcome=outcome):
                self.assertIn(outcome, gate.group(1))

    def test_consent_is_asked_for_separately(self):
        text = (TEMPLATES / "job-sheet.md").read_text()
        for purpose in ("for private records", "social media content", "anonymised case study"):
            with self.subTest(purpose=purpose):
                self.assertIn(purpose, text)


if __name__ == "__main__":
    unittest.main()
