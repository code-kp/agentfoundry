# AgentFoundry

AgentFoundry is the shared backend platform layer for Foundry-style agent apps.

It contains:

- the reusable runtime in `src/core/`
- a public package surface in `src/agent_foundry/`
- shared backend services in `src/services/`
- reusable CLI tooling for scaffolding and embeddings

This repo is intended to be consumed by app repos that provide their own workspace package, bootstrap config, and UI mounting.

## Public Surface

- `agent_foundry.config.FoundryConfig`
- `agent_foundry.api.create_runtime()`
- `agent_foundry.server.create_app()`
- `agent_foundry.cli.*`

## Install

```bash
uv sync --all-groups --all-extras
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

`hey` is the only supported command surface.

```bash
hey start
hey stop
hey create-agent
hey sync-embedding
hey format
hey test
```

App repos should compose `agent_foundry.server.create_app(...)` with a UI package or their own static mounting.

`hey` is the shared project CLI. It reads local project defaults from `[tool.agentfoundry]` in the current repo's `pyproject.toml`.
The lower-level `new_agent.py` and `sync_embeddings.py` modules remain internal implementation details behind `hey`.

## Notes

- This split keeps the shared backend platform in one repo and app-specific agents/tools/skills in separate repos.
- The shared UI now lives in `agentfoundry-ui`.
