import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


def _load_related_metadata_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "vscode-related-tests"
        / "python"
        / "related_tests_metadata.py"
    )
    spec = importlib.util.spec_from_file_location("related_tests_metadata", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load related tests metadata helper from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    return module


_RELATED_METADATA = _load_related_metadata_module()
inspect_source_file = _RELATED_METADATA.inspect_source_file
parse_related_tests = _RELATED_METADATA.parse_related_tests
scan_related_sources = _RELATED_METADATA.scan_related_sources


class RelatedTestsMetadataTest(unittest.TestCase):
    def test_parse_related_tests_reads_bullet_list(self) -> None:
        tests, errors = parse_related_tests(
            """
Tests:
- tests/core/test_guardrails.py
- tests/core/contracts/test_execution.py
""".strip()
        )

        self.assertEqual(
            tests,
            ("tests/core/test_guardrails.py", "tests/core/contracts/test_execution.py"),
        )
        self.assertEqual(errors, ())

    def test_parse_related_tests_rejects_non_test_paths(self) -> None:
        tests, errors = parse_related_tests(
            """
Tests:
- docs/test-plan.md
- tests/core/test_guardrails.py
""".strip()
        )

        self.assertEqual(tests, ("tests/core/test_guardrails.py",))
        self.assertEqual(errors, ("Related test path must stay under tests/: docs/test-plan.md",))

    def test_inspect_source_file_reports_missing_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            source_path = workspace_root / "core" / "guardrails.py"
            source_path.parent.mkdir(parents=True, exist_ok=True)
            source_path.write_text(
                '''"""
Tests:
- tests/core/test_guardrails.py
- tests/core/contracts/test_execution.py
"""

VALUE = 1
''',
                encoding="utf-8",
            )
            (workspace_root / "tests" / "core" / "contracts").mkdir(parents=True)
            (workspace_root / "tests" / "core" / "test_guardrails.py").write_text("", encoding="utf-8")

            metadata = inspect_source_file(source_path, workspace_root)

            self.assertEqual(metadata.source, "core/guardrails.py")
            self.assertEqual(
                metadata.tests,
                ("tests/core/test_guardrails.py", "tests/core/contracts/test_execution.py"),
            )
            self.assertEqual(metadata.missing_tests, ("tests/core/contracts/test_execution.py",))
            self.assertEqual(metadata.errors, ())

    def test_scan_related_sources_only_returns_annotated_modules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            (workspace_root / "tests" / "core").mkdir(parents=True)
            (workspace_root / "tests" / "core" / "test_guardrails.py").write_text("", encoding="utf-8")
            annotated = workspace_root / "core" / "guardrails.py"
            annotated.parent.mkdir(parents=True, exist_ok=True)
            annotated.write_text(
                '''"""
Tests:
- tests/core/test_guardrails.py
"""
''',
                encoding="utf-8",
            )
            plain = workspace_root / "core" / "registry.py"
            plain.write_text("VALUE = 1\n", encoding="utf-8")

            results = scan_related_sources(workspace_root, ("core",))

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].source, "core/guardrails.py")
            self.assertEqual(results[0].tests, ("tests/core/test_guardrails.py",))


if __name__ == "__main__":
    unittest.main()
