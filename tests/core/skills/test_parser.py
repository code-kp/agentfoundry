import tempfile
import unittest
from pathlib import Path

from core.skills.parser import parse_skill_file


class SkillParserTest(unittest.TestCase):
    def test_parses_frontmatter_and_derives_id_from_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skills_root = Path(tmp)
            path = skills_root / "knowledge" / "support" / "triage.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                """---
title: Support Triage
type: workflow
summary: Investigate support issues.
tags: [support, triage]
triggers:
  - issue
  - troubleshoot
mode: auto
priority: 80
requires_tools: [shared_ping]
---

# Support Triage

Confirm the issue and recent changes.
""",
                encoding="utf-8",
            )

            skill = parse_skill_file(path, skills_root)

            self.assertEqual(skill.id, "support.triage")
            self.assertEqual(skill.source, "knowledge/support/triage.md")
            self.assertEqual(skill.skill_class, "knowledge")
            self.assertEqual(skill.skill_type, "workflow")
            self.assertEqual(skill.tags, ("support", "triage"))
            self.assertEqual(skill.triggers, ("issue", "troubleshoot"))
            self.assertEqual(skill.requires_tools, ("shared_ping",))

    def test_parses_markdown_only_behavior_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skills_root = Path(tmp)
            path = skills_root / "behavior" / "support" / "persona.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                """# Support Persona

Use direct language and keep troubleshooting steps concrete.
""",
                encoding="utf-8",
            )

            skill = parse_skill_file(path, skills_root)

            self.assertEqual(skill.id, "support.persona")
            self.assertEqual(skill.skill_class, "behavior")
            self.assertEqual(skill.skill_type, "persona")
            self.assertEqual(skill.mode, "always_on")
            self.assertEqual(skill.title, "Support Persona")
            self.assertIn("troubleshooting steps", skill.summary)


if __name__ == "__main__":
    unittest.main()
