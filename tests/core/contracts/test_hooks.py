import unittest

from core.contracts.hooks import AgentHooks, DEFAULT_AGENT_HOOKS, ensure_agent_hooks


class CustomHooks(AgentHooks):
    pass


class HooksContractsTest(unittest.TestCase):
    def test_returns_default_hooks_when_missing(self) -> None:
        self.assertIs(ensure_agent_hooks(None), DEFAULT_AGENT_HOOKS)

    def test_accepts_agent_hooks_subclasses(self) -> None:
        hooks = CustomHooks()

        self.assertIs(ensure_agent_hooks(hooks), hooks)

    def test_rejects_invalid_hook_types(self) -> None:
        with self.assertRaises(TypeError):
            ensure_agent_hooks("invalid")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
