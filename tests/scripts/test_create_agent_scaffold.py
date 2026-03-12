import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "create_agent_scaffold.py"
)
SPEC = importlib.util.spec_from_file_location("create_agent_scaffold", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class WorkspaceScaffoldTest(unittest.TestCase):
    def test_build_agent_id_uses_namespace_and_agent_name_slug(self) -> None:
        self.assertEqual(
            MODULE.build_agent_id(
                namespace_path="support/refunds",
                agent_name="Refund Assistant",
            ),
            "support.refunds.refund_assistant",
        )

    def test_inspect_workspace_inventory_excludes_implicit_search_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = self._create_workspace(
                Path(tmp), package_name="sandboxspace_inventory"
            )

            inventory = MODULE.inspect_workspace_inventory(
                workspace_root,
                workspace_package="sandboxspace_inventory",
            )

            self.assertIn("existing_lookup", inventory.tool_names)
            self.assertNotIn("search_skills", inventory.tool_names)

    def test_wizard_creates_agent_tool_and_skill_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = self._create_workspace(
                Path(tmp), package_name="sandboxspace_wizard"
            )
            answers = iter(
                [
                    "Refund Assistant",
                    "support/refunds",
                    "Handle refund policy questions and escalation steps",
                    "",
                    "",
                    "orchestrated",
                    "n",
                    "existing_lookup",
                    "y",
                    "lookup_refund_status",
                    "Look up refund status by request id",
                    "support",
                    "Refund status details",
                    "",
                    "",
                    "",
                ]
            )
            prompts: list[str] = []
            output_lines: list[str] = []

            def fake_input(prompt: str) -> str:
                prompts.append(prompt)
                return next(answers)

            result = MODULE.run_agent_scaffold_wizard(
                workspace_root,
                workspace_package="sandboxspace_wizard",
                input_fn=fake_input,
                output_fn=output_lines.append,
            )

            self.assertIsNotNone(result)
            assert result is not None

            agent_path = (
                workspace_root
                / "agents"
                / "support"
                / "refunds"
                / "refund_assistant.py"
            )
            tool_path = workspace_root / "tools" / "lookup_refund_status.py"
            persona_path = (
                workspace_root / "skills" / "behavior" / "support" / "persona.md"
            )
            knowledge_path = (
                workspace_root
                / "skills"
                / "knowledge"
                / "support"
                / "refunds"
                / "refund_assistant.md"
            )
            package_path = (
                workspace_root / "agents" / "support" / "refunds" / "__init__.py"
            )

            self.assertTrue(agent_path.exists())
            self.assertTrue(tool_path.exists())
            self.assertTrue(persona_path.exists())
            self.assertTrue(knowledge_path.exists())
            self.assertTrue(package_path.exists())

            agent_source = agent_path.read_text(encoding="utf-8")
            self.assertIn('runtime_mode = "orchestrated"', agent_source)
            self.assertIn("execution = ExecutionConfig(max_tool_calls=6)", agent_source)
            self.assertIn("memory = DISABLED_MEMORY_CONFIG", agent_source)
            self.assertIn('"existing_lookup"', agent_source)
            self.assertIn('"lookup_refund_status"', agent_source)
            self.assertIn('"support.persona"', agent_source)
            self.assertIn('"support.refunds.refund_assistant"', agent_source)

            tool_source = tool_path.read_text(encoding="utf-8")
            self.assertIn('name = "lookup_refund_status"', tool_source)
            self.assertIn('category = "support"', tool_source)
            self.assertIn("raise NotImplementedError", tool_source)

            self.assertIn("# Support Persona", persona_path.read_text(encoding="utf-8"))
            self.assertIn(
                "# Refund Assistant Reference",
                knowledge_path.read_text(encoding="utf-8"),
            )
            self.assertIn(agent_path, result.primary_files)
            self.assertIn(package_path, result.support_files)
            self.assertTrue(any("Write these files?" in prompt for prompt in prompts))
            self.assertTrue(any("Namespace path" in prompt for prompt in prompts))
            self.assertTrue(
                any("Created scaffold files:" in line for line in output_lines)
            )
            self.assertTrue(
                any("Namespace: support.refunds" in line for line in output_lines)
            )
            self.assertTrue(
                any(
                    line.endswith(
                        "/sandboxspace_wizard/agents/support/refunds/refund_assistant.py"
                    )
                    for line in output_lines
                )
            )

    def _create_workspace(self, root: Path, *, package_name: str) -> Path:
        workspace_root = root / package_name
        self._write(workspace_root / "__init__.py", "")
        self._write(workspace_root / "agents" / "__init__.py", "")
        self._write(workspace_root / "tools" / "__init__.py", "")
        self._write(
            workspace_root / "tools" / "existing_lookup.py",
            """
from core.contracts.tools import ToolModule, register_tool_class


@register_tool_class
class ExistingLookupTool(ToolModule):
    name = "existing_lookup"
    description = "Look up an existing record."

    def run(self, query: str) -> dict:
        return {"query": query}
""".strip(),
        )
        return workspace_root

    def _write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content + ("\n" if content else ""), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
