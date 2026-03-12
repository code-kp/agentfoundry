from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FoundryConfig:
    workspace_root: Path
    workspace_package: str = "workspace"
    data_root: Path | None = None
    env_path: Path | None = None
    app_name: str = "AgentFoundry"

    def __post_init__(self) -> None:
        workspace_root = Path(self.workspace_root).resolve()
        workspace_package = str(self.workspace_package or "").strip() or "workspace"
        data_root = (
            Path(self.data_root).resolve()
            if self.data_root is not None
            else _default_data_root(workspace_root, workspace_package)
        )
        env_path = Path(self.env_path).resolve() if self.env_path is not None else None

        object.__setattr__(self, "workspace_root", workspace_root)
        object.__setattr__(self, "workspace_package", workspace_package)
        object.__setattr__(self, "data_root", data_root)
        object.__setattr__(self, "env_path", env_path)
        object.__setattr__(self, "app_name", str(self.app_name or "").strip() or "AgentFoundry")

    @property
    def conversations_root(self) -> Path:
        return self.data_root / ".conversations"

    @property
    def embeddings_root(self) -> Path:
        return self.data_root / ".embeddings"


def _default_data_root(workspace_root: Path, workspace_package: str) -> Path:
    package_depth = len([part for part in workspace_package.split(".") if part.strip()])
    parents = list(workspace_root.parents)
    if package_depth >= len(parents):
        return workspace_root.parent
    import_root = parents[max(package_depth - 1, 0)]
    if import_root.name == "src":
        return import_root.parent
    return import_root
