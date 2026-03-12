from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentRecord:
    agent_id: str
    module_name: str
    agent_name: str
    project_name: str
    project_root: Path
    fingerprint: str
    data_root: Path | None = None

    def __post_init__(self) -> None:
        if self.data_root is None:
            object.__setattr__(self, "data_root", self.project_root)
