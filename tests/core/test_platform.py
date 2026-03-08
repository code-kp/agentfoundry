import unittest
from pathlib import Path

from core.platform import AgentPlatform


class AgentPlatformTest(unittest.TestCase):
    def test_catalog_lists_web_agents(self) -> None:
        platform = AgentPlatform(Path("workspace"))
        catalog = platform.catalog()
        agent_ids = [agent["id"] for agent in catalog["agents"]]

        self.assertIn("web.answer", agent_ids)
        self.assertIn("web.research", agent_ids)


if __name__ == "__main__":
    unittest.main()
