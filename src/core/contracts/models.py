from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache


LITELLM_PREFIX = "litellm:"
_KNOWN_PROVIDER_PREFIXES = (
    "anthropic/",
    "azure/",
    "bedrock/",
    "cerebras/",
    "cohere/",
    "deepseek/",
    "gemini/",
    "google/",
    "groq/",
    "mistral/",
    "ollama/",
    "openai/",
    "openrouter/",
    "perplexity/",
    "vertex_ai/",
    "xai/",
)


@dataclass(frozen=True)
class AvailableModel:
    id: str
    hash: str
    label: str
    model_name: str
    description: str = ""


_AVAILABLE_MODEL_DEFINITIONS = (
    (
        "Gemini 3.1 Flash Lite",
        "gemini-3.1-flash-lite-preview",
        "Fast, low-cost Gemini preview model.",
    ),
    (
        "Gemini 2.5 Flash",
        "gemini-2.5-flash",
        "Balanced Gemini flash model.",
    ),
    (
        "Gemini 2.0 Flash",
        "gemini-2.0-flash",
        "Stable Gemini flash baseline.",
    ),
    (
        "GPT-4o Mini",
        "litellm:openai/gpt-4o-mini",
        "OpenAI model routed through LiteLLM.",
    ),
)


def lite_llm_model(model_name: str) -> str:
    normalized = normalize_lite_llm_reference(model_name)
    return "{prefix}{model}".format(prefix=LITELLM_PREFIX, model=normalized)


def is_lite_llm_model(model_name: str | None) -> bool:
    normalized = str(model_name or "").strip().lower()
    return normalized.startswith(LITELLM_PREFIX)


def strip_lite_llm_prefix(model_name: str) -> str:
    normalized = str(model_name or "").strip()
    if is_lite_llm_model(normalized):
        return normalized[len(LITELLM_PREFIX) :].strip()
    return normalized


def normalize_lite_llm_reference(model_name: str) -> str:
    normalized = strip_lite_llm_prefix(model_name)
    if not normalized:
        raise ValueError("LiteLLM model name cannot be blank.")

    lowered = normalized.lower()
    if lowered.startswith(_KNOWN_PROVIDER_PREFIXES):
        return normalized

    if lowered.startswith("gemini"):
        return "gemini/{model}".format(model=normalized)

    raise ValueError(
        "LiteLLM models must use an explicit provider/model reference such as "
        "`openai/gpt-4o-mini`, `anthropic/claude-3-7-sonnet`, or "
        "`gemini/gemini-2.0-flash`."
    )


def normalize_model_reference(
    model_name: str | None,
    *,
    model_backend: str | None = None,
) -> str:
    normalized = str(model_name or "").strip()
    if not normalized:
        return ""
    if is_lite_llm_model(normalized):
        return normalized
    if str(model_backend or "").strip().lower() == "litellm":
        return lite_llm_model(normalized)
    return normalized


def _model_hash(model_name: str) -> str:
    return hashlib.sha256(model_name.encode("utf-8")).hexdigest()[:10]


@lru_cache(maxsize=1)
def available_models() -> tuple[AvailableModel, ...]:
    models: list[AvailableModel] = []
    seen_ids: set[str] = set()
    for label, model_name, description in _AVAILABLE_MODEL_DEFINITIONS:
        normalized_model_name = normalize_model_reference(model_name)
        model_hash = _model_hash(normalized_model_name)
        model_id = "mdl_{value}".format(value=model_hash)
        if model_id in seen_ids:
            raise ValueError(
                "Duplicate model catalog id generated for {model_name}".format(
                    model_name=normalized_model_name
                )
            )
        seen_ids.add(model_id)
        models.append(
            AvailableModel(
                id=model_id,
                hash=model_hash,
                label=label,
                model_name=normalized_model_name,
                description=description,
            )
        )
    return tuple(models)


def serialize_available_models() -> list[dict[str, str]]:
    return [
        {
            "id": item.id,
            "hash": item.hash,
            "label": item.label,
            "description": item.description,
        }
        for item in available_models()
    ]


def find_available_model(*, model_id: str | None = None) -> AvailableModel | None:
    normalized_id = str(model_id or "").strip()
    if not normalized_id:
        return None
    for item in available_models():
        if item.id == normalized_id:
            return item
    return None


def find_available_model_by_reference(
    model_name: str | None,
) -> AvailableModel | None:
    normalized_model_name = str(model_name or "").strip()
    if not normalized_model_name:
        return None

    lowered = normalized_model_name.lower()
    for item in available_models():
        aliases = {item.model_name.lower()}
        if is_lite_llm_model(item.model_name):
            aliases.add(strip_lite_llm_prefix(item.model_name).lower())
        if lowered in aliases:
            return item
    return None


def resolve_model_selection(
    *,
    model_id: str | None = None,
    model_name: str | None = None,
) -> str | None:
    normalized_model_name = str(model_name or "").strip()
    if normalized_model_name:
        return normalized_model_name

    selected = find_available_model(model_id=model_id)
    if selected is None:
        normalized_id = str(model_id or "").strip()
        if normalized_id:
            raise ValueError(
                "Unknown model selection: {model_id}".format(model_id=normalized_id)
            )
        return None
    return selected.model_name


def public_model_label(
    model_name: str | None,
    *,
    fallback: str = "",
) -> str:
    selected = find_available_model_by_reference(model_name)
    if selected is not None:
        return selected.label
    return str(fallback or "").strip()
