# AgentFoundry

AgentFoundry is the shared platform layer for Foundry-style agent apps.

It contains:

- the reusable runtime in `src/core/`
- a public package surface in `src/agent_foundry/`
- shared backend services in `src/services/`
- the shared React UI in `frontend/`
- a packaged frontend build served by the shared FastAPI app
- reusable CLI tooling for scaffolding, embeddings, and dev orchestration

This repo is intended to be consumed by app repos that provide their own workspace package and bootstrap config.

## Public Surface

- `agent_foundry.config.FoundryConfig`
- `agent_foundry.api.create_runtime()`
- `agent_foundry.server.create_app()`
- `agent_foundry.cli.*`

## Install

```bash
uv sync --all-groups --all-extras
uv run poe frontend-install
uv run poe frontend-build
```

## Example Usage

```python
from pathlib import Path

from agent_foundry.config import FoundryConfig
from agent_foundry.server import create_app


app = create_app(
    FoundryConfig(
        app_name="My App",
        workspace_root=Path("src/my_app/workspace"),
        workspace_package="my_app.workspace",
        data_root=Path("."),
    )
)
```

## CLI

```bash
uv run foundry-new-agent --workspace-root src/my_app/workspace --workspace-package my_app.workspace
uv run foundry-sync-embeddings --workspace-root src/my_app/workspace --data-root .
uv run foundry-dev run
```

App repos that call `agent_foundry.server.create_app(...)` will serve the packaged UI at `/` when the frontend build is present.

## Notes

- This split keeps the shared platform in one repo and app-specific agents/tools/skills in separate repos.
- Use `uv run poe frontend` only when developing the shared UI itself.
