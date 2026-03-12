from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path

from fastapi import HTTPException
from starlette.requests import Request
from starlette.staticfiles import StaticFiles


def packaged_web_dist() -> Path | None:
    root = _package_root()
    bundled = root / "web" / "dist"
    if bundled.is_dir():
        return bundled

    repo_dist = root.parent.parent.parent / "frontend" / "dist"
    if repo_dist.is_dir():
        return repo_dist
    return None


class SinglePageAppFiles(StaticFiles):
    def __init__(self, directory: str | Path) -> None:
        super().__init__(directory=str(directory), html=True)

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code != 404:
            return response

        request = Request(scope)
        if request.url.path.startswith("/api/"):
            raise HTTPException(status_code=404)
        return await super().get_response("index.html", scope)


def _package_root() -> Path:
    with as_file(files("agent_foundry")) as package_root:
        return Path(package_root)
