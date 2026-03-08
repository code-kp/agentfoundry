import unittest
from pathlib import Path

from core.execution.orchestrated.runtime import OrchestratedAgentRuntime
from core.platform import AgentPlatform


class OrchestratedRuntimeTest(unittest.TestCase):
    def test_web_research_uses_orchestrated_runtime(self) -> None:
        platform = AgentPlatform(Path("workspace"))
        runtime = platform._runtimes["web.research"]

        self.assertIsInstance(runtime, OrchestratedAgentRuntime)


if __name__ == "__main__":
    unittest.main()
