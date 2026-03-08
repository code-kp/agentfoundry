import unittest
from pathlib import Path

from core.contracts.skills import SkillDefinition, ensure_skill_ids, ensure_skill_scopes


class SkillContractsTest(unittest.TestCase):
    def test_scope_helpers_normalize_and_dedupe_values(self) -> None:
        self.assertEqual(
            ensure_skill_scopes(("support", "support", "support/triage")),
            ("support", "support.triage"),
        )
        self.assertEqual(
            ensure_skill_ids(("support/triage", "support.triage")),
            ("support.triage",),
        )

    def test_skill_definition_matches_parent_scope_and_globs(self) -> None:
        skill = SkillDefinition(
            id="support.triage",
            source="support/triage.md",
            path=Path("support/triage.md"),
            title="Support Triage",
            skill_type="workflow",
            summary="Troubleshoot incidents.",
        )

        self.assertTrue(skill.matches_scope("support"))
        self.assertTrue(skill.matches_scope("support.*"))
        self.assertFalse(skill.matches_scope("billing"))

    def test_skill_definition_can_record_behavior_class(self) -> None:
        skill = SkillDefinition(
            id="support.persona",
            source="behavior/support/persona.md",
            path=Path("behavior/support/persona.md"),
            title="Support Persona",
            skill_type="persona",
            summary="Keep replies concrete.",
            skill_class="behavior",
        )

        self.assertTrue(skill.is_behavior)
        self.assertFalse(skill.is_knowledge)


if __name__ == "__main__":
    unittest.main()
