import sys
import types
import unittest
from unittest import mock

import core.execution.shared.models as shared_models


class _StubLiteLlm:
    def __init__(self, *, model: str) -> None:
        self.model = model


class ModelResolutionTest(unittest.TestCase):
    def test_resolve_native_model_returns_raw_string(self) -> None:
        resolved = shared_models.resolve_model("gemini-2.0-flash")

        self.assertEqual(resolved.backend, "native")
        self.assertEqual(resolved.display_name, "gemini-2.0-flash")
        self.assertEqual(resolved.adk_model, "gemini-2.0-flash")

    def test_resolve_litellm_model_wraps_adk_litellm_adapter(self) -> None:
        fake_module = types.ModuleType("google.adk.models.lite_llm")
        fake_module.LiteLlm = _StubLiteLlm

        with mock.patch.dict(sys.modules, {"google.adk.models.lite_llm": fake_module}):
            resolved = shared_models.resolve_model("litellm:openai/gpt-4o-mini")

        self.assertEqual(resolved.backend, "litellm")
        self.assertEqual(resolved.display_name, "litellm:openai/gpt-4o-mini")
        self.assertIsInstance(resolved.adk_model, _StubLiteLlm)
        self.assertEqual(resolved.adk_model.model, "openai/gpt-4o-mini")

    def test_resolve_litellm_gemini_model_normalizes_to_gemini_provider(self) -> None:
        fake_module = types.ModuleType("google.adk.models.lite_llm")
        fake_module.LiteLlm = _StubLiteLlm

        with mock.patch.dict(sys.modules, {"google.adk.models.lite_llm": fake_module}):
            resolved = shared_models.resolve_model("litellm:gemini-2.0-flash")

        self.assertEqual(resolved.display_name, "litellm:gemini/gemini-2.0-flash")
        self.assertEqual(resolved.adk_model.model, "gemini/gemini-2.0-flash")

    def test_resolve_litellm_requires_explicit_provider_for_non_gemini_models(self) -> None:
        with self.assertRaises(ValueError) as context:
            shared_models.resolve_model("litellm:gpt-4o-mini")

        self.assertIn("explicit provider/model reference", str(context.exception))

    def test_resolve_litellm_model_reports_missing_dependency_cleanly(self) -> None:
        with mock.patch.dict(sys.modules, {"google.adk.models.lite_llm": None}):
            with self.assertRaises(RuntimeError) as context:
                shared_models.resolve_model("litellm:openai/gpt-4o-mini")

        self.assertIn("LiteLLM models require", str(context.exception))

    def test_describe_model_error_sanitizes_vertex_credential_failure(self) -> None:
        message = shared_models.describe_model_error(
            RuntimeError("Failed to load vertex credentials. Your default credentials were not found."),
            model_reference="litellm:gemini/gemini-2.0-flash",
        )

        self.assertIn("Google AI Studio", message)
        self.assertNotIn("Traceback", message)


if __name__ == "__main__":
    unittest.main()
