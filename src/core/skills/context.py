from __future__ import annotations

import contextvars
from pathlib import Path
from typing import Optional

from core.skills.store import SkillStore


_current_skill_store: contextvars.ContextVar[Optional[SkillStore]] = (
    contextvars.ContextVar(
        "current_skill_store",
        default=None,
    )
)

_current_skill_embeddings_root: contextvars.ContextVar[Optional[Path]] = (
    contextvars.ContextVar(
        "current_skill_embeddings_root",
        default=None,
    )
)


def bind_skill_store(store: SkillStore) -> contextvars.Token:
    return _current_skill_store.set(store)


def reset_skill_store(token: contextvars.Token) -> None:
    _current_skill_store.reset(token)


def bind_skill_embeddings_root(embeddings_root: Path | None) -> contextvars.Token:
    return _current_skill_embeddings_root.set(embeddings_root)


def reset_skill_embeddings_root(token: contextvars.Token) -> None:
    _current_skill_embeddings_root.reset(token)


def current_skill_store() -> SkillStore:
    store = _current_skill_store.get()
    if store is None:
        raise RuntimeError(
            "No active skill store is bound to the current runtime context."
        )
    return store


def current_skill_embeddings_root() -> Path | None:
    return _current_skill_embeddings_root.get()
