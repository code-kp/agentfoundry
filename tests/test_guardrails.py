import unittest

from core.contracts.execution import ExecutionConfig
from core.guardrails import ToolLoopGuardrails


class ToolLoopGuardrailsTest(unittest.TestCase):
    def test_blocks_duplicate_call_arguments_within_window(self) -> None:
        guardrails = ToolLoopGuardrails(
            ExecutionConfig(
                max_tool_calls=8,
                max_calls_per_tool=3,
                max_consecutive_calls_per_tool=3,
                block_duplicate_call_arguments=True,
                duplicate_call_window=4,
            )
        )

        first = guardrails.authorize("search_web", {"query": "latest OpenAI news"})
        second = guardrails.authorize("search_web", {"query": "latest OpenAI news"})

        self.assertIsNone(first)
        self.assertIn("already tried", second or "")

    def test_blocks_when_total_tool_budget_is_reached(self) -> None:
        guardrails = ToolLoopGuardrails(
            ExecutionConfig(
                max_tool_calls=1,
                max_calls_per_tool=3,
                max_consecutive_calls_per_tool=3,
                duplicate_call_window=4,
            )
        )

        first = guardrails.authorize("search_web", {"query": "latest OpenAI news"})
        second = guardrails.authorize("fetch_web_page", {"url": "https://example.com"})

        self.assertIsNone(first)
        self.assertIn("tool-call budget", second or "")


if __name__ == "__main__":
    unittest.main()
