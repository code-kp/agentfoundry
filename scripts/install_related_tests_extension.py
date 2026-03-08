#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
EXTENSION_DIR = ROOT_DIR / "vscode-related-tests"


def main() -> int:
    manifest = load_manifest()
    extensions_dir = resolve_extensions_dir()
    target_dir = extensions_dir / build_extension_dir_name(manifest)

    extensions_dir.mkdir(parents=True, exist_ok=True)
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(EXTENSION_DIR, target_dir)

    print("Installed Related Tests Controller to {path}".format(path=target_dir))
    print("Reload VS Code to see the Related Tests controller in the Testing pane.")
    return 0


def load_manifest() -> dict:
    manifest_path = EXTENSION_DIR / "package.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def build_extension_dir_name(manifest: dict) -> str:
    publisher = str(manifest.get("publisher") or "").strip()
    name = str(manifest.get("name") or "").strip()
    version = str(manifest.get("version") or "").strip()
    if not publisher or not name or not version:
        raise ValueError("vscode-related-tests/package.json is missing publisher, name, or version.")
    return "{publisher}.{name}-{version}".format(
        publisher=publisher,
        name=name,
        version=version,
    )


def resolve_extensions_dir() -> Path:
    override = str(os.getenv("VSCODE_EXTENSIONS_DIR") or "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".vscode" / "extensions"


if __name__ == "__main__":
    raise SystemExit(main())
