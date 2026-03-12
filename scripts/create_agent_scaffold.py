#!/usr/bin/env python3
# ruff: noqa: E402
from __future__ import annotations

import re
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.contracts.tools import ToolDefinition
from core.discovery import DiscoveryService
from core.registry import Register


_ID_SPLIT_RE = re.compile(r"[./]+")
_NON_IDENTIFIER_RE = re.compile(r"[^a-z0-9]+")
_TITLE_SPLIT_RE = re.compile(r"[^a-zA-Z0-9]+")
_STYLE_GUIDANCE = {
    "concise": "Prefer short, direct answers with only the detail needed to move the task forward.",
    "balanced": "Give clear, moderately detailed answers that stay focused on the user's goal.",
    "detailed": "Give thorough answers with enough explanation for implementation work and handoff.",
}


@dataclass(frozen=True)
class WorkspaceInventory:
    agent_ids: tuple[str, ...]
    tool_names: tuple[str, ...]
    behavior_skill_ids: tuple[str, ...]
    knowledge_skill_ids: tuple[str, ...]


@dataclass(frozen=True)
class SkillScaffold:
    skill_id: str
    skill_class: str
    title: str
    summary: str


@dataclass(frozen=True)
class ToolScaffold:
    tool_name: str
    description: str
    category: str
    returns: str


@dataclass(frozen=True)
class AgentScaffoldPlan:
    agent_name: str
    namespace_path: str
    agent_id: str
    description: str
    responsibility: str
    answer_style: str
    runtime_mode: str
    memory_enabled: bool
    tool_names: tuple[str, ...]
    behavior_skill_ids: tuple[str, ...]
    knowledge_skill_ids: tuple[str, ...]
    skill_stubs: tuple[SkillScaffold, ...] = ()
    tool_stub: ToolScaffold | None = None


@dataclass(frozen=True)
class ScaffoldWriteResult:
    primary_files: tuple[Path, ...]
    support_files: tuple[Path, ...]


def inspect_workspace_inventory(
    workspace_root: Path, *, workspace_package: str | None = None
) -> WorkspaceInventory:
    discovery = DiscoveryService(
        workspace_root=workspace_root,
        workspace_package=workspace_package or workspace_root.name,
    )
    discovered_skills = discovery.discover_skills()
    discovered_agents = discovery.discover_agents()
    tool_names = tuple(
        sorted(
            name
            for name in Register.items(ToolDefinition).keys()
            if name != "search_skills"
        )
    )
    behavior_skill_ids = tuple(
        sorted(
            item.skill_id
            for item in discovered_skills.values()
            if item.definition.is_behavior
        )
    )
    knowledge_skill_ids = tuple(
        sorted(
            item.skill_id
            for item in discovered_skills.values()
            if item.definition.is_knowledge
        )
    )
    return WorkspaceInventory(
        agent_ids=tuple(sorted(discovered_agents.keys())),
        tool_names=tool_names,
        behavior_skill_ids=behavior_skill_ids,
        knowledge_skill_ids=knowledge_skill_ids,
    )


def normalize_agent_id(value: str, *, fallback: str = "agent") -> str:
    raw = str(value or "").strip()
    if not raw:
        return fallback
    parts = [
        _normalize_identifier_segment(segment, fallback=fallback)
        for segment in _ID_SPLIT_RE.split(raw)
        if segment.strip()
    ]
    return ".".join(part for part in parts if part) or fallback


def normalize_tool_name(value: str, *, fallback: str = "tool") -> str:
    return _normalize_identifier_segment(value, fallback=fallback)


def build_agent_id(*, namespace_path: str, agent_name: str) -> str:
    module_name = normalize_agent_id(agent_name)
    namespace = normalize_namespace_path(namespace_path)
    if not namespace:
        return module_name
    return "{namespace}.{module_name}".format(
        namespace=namespace, module_name=module_name
    )


def normalize_namespace_path(value: str) -> str:
    return (
        normalize_agent_id(value, fallback="namespace")
        if str(value or "").strip()
        else ""
    )


def render_agent_module(plan: AgentScaffoldPlan) -> str:
    imports = ["from core.contracts.agent import AgentModule, register_agent_class"]
    if plan.runtime_mode == "orchestrated":
        imports.append("from core.contracts.execution import ExecutionConfig")
    if not plan.memory_enabled:
        imports.append("from core.contracts.memory import DISABLED_MEMORY_CONFIG")

    lines = [
        "from __future__ import annotations",
        "",
        *imports,
        "",
        "",
        "@register_agent_class",
        "class {class_name}(AgentModule):".format(
            class_name=_pascal_case(plan.agent_name) or "GeneratedAgent"
        ),
        '    name = "{name}"'.format(name=_escape_python_string(plan.agent_name)),
        '    description = "{description}"'.format(
            description=_escape_python_string(plan.description)
        ),
        "    system_prompt = {system_prompt}".format(
            system_prompt=_format_string_expression(
                _build_system_prompt(plan), indent="    "
            )
        ),
        "    tools = {tools}".format(
            tools=_format_string_tuple(plan.tool_names, indent="    ")
        ),
        "    behavior = {behavior}".format(
            behavior=_format_string_tuple(plan.behavior_skill_ids, indent="    ")
        ),
        "    knowledge = {knowledge}".format(
            knowledge=_format_string_tuple(plan.knowledge_skill_ids, indent="    ")
        ),
        '    runtime_mode = "{runtime_mode}"'.format(runtime_mode=plan.runtime_mode),
    ]
    if plan.runtime_mode == "orchestrated":
        lines.append("    execution = ExecutionConfig(max_tool_calls=6)")
    if not plan.memory_enabled:
        lines.append("    memory = DISABLED_MEMORY_CONFIG")
    return "\n".join(lines) + "\n"


def render_tool_module(tool: ToolScaffold) -> str:
    lines = [
        "from __future__ import annotations",
        "",
        "from core.contracts.tools import ToolModule, register_tool_class",
        "",
        "",
        "@register_tool_class",
        "class {class_name}(ToolModule):".format(
            class_name=_pascal_case(tool.tool_name) or "GeneratedTool"
        ),
        '    name = "{name}"'.format(name=_escape_python_string(tool.tool_name)),
        '    description = "{description}"'.format(
            description=_escape_python_string(tool.description)
        ),
        '    category = "{category}"'.format(
            category=_escape_python_string(tool.category)
        ),
        "    use_when = (",
        '        "The agent needs data or side effects that are not already available in skills or conversation context.",',
        "    )",
        '    returns = "{returns}"'.format(returns=_escape_python_string(tool.returns)),
        "",
        "    def run(self, query: str) -> dict:",
        '        self.progress.think("Starting {name}", detail="Replace this scaffold with the real integration.", step_id="{name}")'.format(
            name=tool.tool_name
        ),
        '        raise NotImplementedError("Implement {name} before using this tool.")'.format(
            name=tool.tool_name
        ),
    ]
    return "\n".join(lines) + "\n"


def render_skill_markdown(plan: AgentScaffoldPlan, stub: SkillScaffold) -> str:
    if stub.skill_class == "behavior":
        lines = [
            "# {title}".format(title=stub.title),
            "",
            "Behavior guidance for {name}.".format(name=plan.agent_name),
            "",
            "- {style}".format(style=_STYLE_GUIDANCE[plan.answer_style]),
            "- Keep the work centered on this goal: {goal}".format(
                goal=_ensure_sentence(plan.responsibility)
            ),
            "- Separate confirmed facts from assumptions.",
            "- Use tools only when they materially improve accuracy, freshness, or task completion.",
        ]
        return "\n".join(lines) + "\n"

    lines = [
        "# {title}".format(title=stub.title),
        "",
        "Reference material for {name}.".format(name=plan.agent_name),
        "",
        _ensure_sentence(stub.summary or plan.responsibility),
        "",
        "## Key Facts",
        "",
        "- Add the concrete facts this agent should rely on.",
        "- Keep each fact stable, specific, and easy to verify.",
        "",
        "## Workflow",
        "",
        "1. Add the common request flow or decision sequence.",
        "2. Note edge cases, escalation rules, or required approvals.",
    ]
    return "\n".join(lines) + "\n"


def planned_primary_paths(
    workspace_root: Path, plan: AgentScaffoldPlan
) -> tuple[Path, ...]:
    paths = [_agent_module_path(workspace_root, plan.agent_id)]
    if plan.tool_stub is not None:
        paths.append(_tool_module_path(workspace_root, plan.tool_stub.tool_name))
    for stub in plan.skill_stubs:
        paths.append(_skill_path(workspace_root, stub))
    return tuple(paths)


def write_agent_scaffold(
    workspace_root: Path, plan: AgentScaffoldPlan
) -> ScaffoldWriteResult:
    conflicts = [
        path for path in planned_primary_paths(workspace_root, plan) if path.exists()
    ]
    if conflicts:
        raise FileExistsError(
            "Refusing to overwrite existing scaffold file(s): {paths}".format(
                paths=", ".join(str(path) for path in conflicts)
            )
        )

    support_files: list[Path] = []
    primary_files: list[Path] = []

    support_files.extend(_ensure_package_root(workspace_root / "tools"))
    support_files.extend(
        _ensure_agent_packages(workspace_root / "agents", plan.agent_id.split(".")[:-1])
    )

    agent_path = _agent_module_path(workspace_root, plan.agent_id)
    _write_text(agent_path, render_agent_module(plan))
    primary_files.append(agent_path)

    if plan.tool_stub is not None:
        tool_path = _tool_module_path(workspace_root, plan.tool_stub.tool_name)
        _write_text(tool_path, render_tool_module(plan.tool_stub))
        primary_files.append(tool_path)

    for stub in plan.skill_stubs:
        skill_path = _skill_path(workspace_root, stub)
        _write_text(skill_path, render_skill_markdown(plan, stub))
        primary_files.append(skill_path)

    return ScaffoldWriteResult(
        primary_files=tuple(primary_files),
        support_files=tuple(support_files),
    )


def run_agent_scaffold_wizard(
    workspace_root: Path,
    *,
    workspace_package: str | None = None,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> ScaffoldWriteResult | None:
    inventory = inspect_workspace_inventory(
        workspace_root, workspace_package=workspace_package
    )

    output_fn("Agent Scaffold")
    output_fn("This wizard creates a starter agent plus optional skill and tool stubs.")
    output_fn("It uses deterministic templates, so no model call is required.")
    output_fn(
        "Use namespace paths like namespace_org1/namespace_level2. The module file name comes from the agent name."
    )
    output_fn("")

    agent_name = _prompt_required("Agent name", input_fn=input_fn)
    default_namespace = ""
    while True:
        namespace_path = normalize_namespace_path(
            _prompt(
                "Namespace path (optional, for example namespace_org1/namespace_level2)",
                default=default_namespace,
                input_fn=input_fn,
            )
        )
        agent_id = build_agent_id(namespace_path=namespace_path, agent_name=agent_name)
        if agent_id in inventory.agent_ids:
            output_fn(
                "Agent id already exists: {agent_id}. Choose another namespace or agent name.".format(
                    agent_id=agent_id
                )
            )
            continue
        break

    responsibility = _prompt_required("Primary responsibility", input_fn=input_fn)
    description = _ensure_sentence(
        _prompt_or_default(
            "Short description",
            default=responsibility,
            input_fn=input_fn,
        )
    )
    answer_style = _prompt_choice(
        "Answer style",
        choices=("concise", "balanced", "detailed"),
        default="balanced",
        input_fn=input_fn,
    )
    runtime_mode = _prompt_choice(
        "Runtime mode",
        choices=("direct", "orchestrated"),
        default="direct",
        input_fn=input_fn,
    )
    memory_enabled = _prompt_yes_no(
        "Enable rolling memory?", default=True, input_fn=input_fn
    )

    output_fn("")
    selected_tools = _prompt_multi_select(
        "Existing tools",
        inventory.tool_names,
        default=(),
        input_fn=input_fn,
        output_fn=output_fn,
    )

    tool_stub: ToolScaffold | None = None
    if _prompt_yes_no("Create a new tool stub?", default=False, input_fn=input_fn):
        default_tool_name = normalize_tool_name(agent_id.replace(".", "_"))
        while True:
            tool_name = normalize_tool_name(
                _prompt("New tool name", default=default_tool_name, input_fn=input_fn),
                fallback=default_tool_name,
            )
            if tool_name in inventory.tool_names or tool_name in selected_tools:
                output_fn(
                    "Tool name already exists in the workspace or this scaffold: {name}".format(
                        name=tool_name
                    )
                )
                continue
            break
        tool_stub = ToolScaffold(
            tool_name=tool_name,
            description=_ensure_sentence(
                _prompt_or_default(
                    "New tool description",
                    default="Describe what {name} should do".format(name=tool_name),
                    input_fn=input_fn,
                )
            ),
            category=_prompt_or_default(
                "New tool category", default="general", input_fn=input_fn
            ),
            returns=_ensure_sentence(
                _prompt_or_default(
                    "New tool return shape",
                    default="A JSON payload with the requested result",
                    input_fn=input_fn,
                )
            ),
        )
        selected_tools = _merge_unique(selected_tools, (tool_name,))

    output_fn("")
    persona_skill_id = "{namespace}.persona".format(namespace=agent_id.split(".", 1)[0])
    behavior_default = (
        (persona_skill_id,) if persona_skill_id in inventory.behavior_skill_ids else ()
    )
    selected_behavior = _prompt_multi_select(
        "Behavior skills",
        inventory.behavior_skill_ids,
        default=behavior_default,
        input_fn=input_fn,
        output_fn=output_fn,
    )

    skill_stubs: list[SkillScaffold] = []
    if (
        persona_skill_id not in inventory.behavior_skill_ids
        and persona_skill_id not in selected_behavior
        and _prompt_yes_no(
            "Create a persona skill stub ({skill_id})?".format(
                skill_id=persona_skill_id
            ),
            default=True,
            input_fn=input_fn,
        )
    ):
        selected_behavior = _merge_unique(selected_behavior, (persona_skill_id,))
        skill_stubs.append(
            SkillScaffold(
                skill_id=persona_skill_id,
                skill_class="behavior",
                title="{title} Persona".format(
                    title=_titleize(agent_id.split(".", 1)[0])
                ),
                summary=responsibility,
            )
        )

    output_fn("")
    knowledge_default = (agent_id,) if agent_id in inventory.knowledge_skill_ids else ()
    selected_knowledge = _prompt_multi_select(
        "Knowledge skills",
        inventory.knowledge_skill_ids,
        default=knowledge_default,
        input_fn=input_fn,
        output_fn=output_fn,
    )

    if (
        agent_id not in inventory.knowledge_skill_ids
        and agent_id not in selected_knowledge
        and _prompt_yes_no(
            "Create a knowledge skill stub ({skill_id})?".format(skill_id=agent_id),
            default=True,
            input_fn=input_fn,
        )
    ):
        selected_knowledge = _merge_unique(selected_knowledge, (agent_id,))
        skill_stubs.append(
            SkillScaffold(
                skill_id=agent_id,
                skill_class="knowledge",
                title="{name} Reference".format(name=agent_name),
                summary=responsibility,
            )
        )

    plan = AgentScaffoldPlan(
        agent_name=agent_name,
        namespace_path=namespace_path,
        agent_id=agent_id,
        description=description,
        responsibility=responsibility,
        answer_style=answer_style,
        runtime_mode=runtime_mode,
        memory_enabled=memory_enabled,
        tool_names=selected_tools,
        behavior_skill_ids=selected_behavior,
        knowledge_skill_ids=selected_knowledge,
        skill_stubs=tuple(skill_stubs),
        tool_stub=tool_stub,
    )

    collisions = [
        path for path in planned_primary_paths(workspace_root, plan) if path.exists()
    ]
    output_fn("")
    output_fn("Scaffold summary")
    output_fn(
        "  Namespace: {namespace}".format(namespace=plan.namespace_path or "(root)")
    )
    output_fn(
        "  Agent module path: {path}".format(
            path=_display_path(_agent_module_path(workspace_root, plan.agent_id))
        )
    )
    output_fn("  Agent id: {agent_id}".format(agent_id=plan.agent_id))
    output_fn("  Runtime: {runtime}".format(runtime=plan.runtime_mode))
    output_fn(
        "  Tools: {items}".format(
            items=", ".join(plan.tool_names) if plan.tool_names else "(none)"
        )
    )
    output_fn(
        "  Behavior: {items}".format(
            items=", ".join(plan.behavior_skill_ids)
            if plan.behavior_skill_ids
            else "(none)"
        )
    )
    output_fn(
        "  Knowledge: {items}".format(
            items=", ".join(plan.knowledge_skill_ids)
            if plan.knowledge_skill_ids
            else "(none)"
        )
    )
    output_fn(
        "  Memory: {state}".format(state="enabled" if memory_enabled else "disabled")
    )
    output_fn("  Files to create:")
    for path in planned_primary_paths(workspace_root, plan):
        output_fn("    - {path}".format(path=_display_path(path)))

    if collisions:
        output_fn("")
        output_fn("The scaffold would overwrite existing files:")
        for path in collisions:
            output_fn("  - {path}".format(path=_display_path(path)))
        output_fn("Rerun the command with a different agent id or tool name.")
        return None

    output_fn("")
    if not _prompt_yes_no("Write these files?", default=True, input_fn=input_fn):
        output_fn("Scaffold cancelled. No files were written.")
        return None

    result = write_agent_scaffold(workspace_root, plan)
    output_fn("")
    output_fn("Created scaffold files:")
    for path in result.primary_files:
        output_fn("  - {path}".format(path=_display_path(path)))
    if result.support_files:
        output_fn("Created package files:")
        for path in result.support_files:
            output_fn("  - {path}".format(path=_display_path(path)))
    return result


def _agent_module_path(workspace_root: Path, agent_id: str) -> Path:
    parts = agent_id.split(".")
    if len(parts) == 1:
        return workspace_root / "agents" / "{name}.py".format(name=parts[0])
    return (
        workspace_root
        / "agents"
        / Path(*parts[:-1])
        / "{name}.py".format(name=parts[-1])
    )


def _tool_module_path(workspace_root: Path, tool_name: str) -> Path:
    return workspace_root / "tools" / "{name}.py".format(name=tool_name)


def _skill_path(workspace_root: Path, stub: SkillScaffold) -> Path:
    parts = stub.skill_id.split(".")
    return (
        workspace_root
        / "skills"
        / stub.skill_class
        / Path(*parts[:-1])
        / "{name}.md".format(name=parts[-1])
    )


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _ensure_agent_packages(
    agents_root: Path, package_parts: Sequence[str]
) -> list[Path]:
    created: list[Path] = []
    created.extend(_ensure_package_root(agents_root))
    current = agents_root
    for part in package_parts:
        current = current / part
        current.mkdir(parents=True, exist_ok=True)
        init_path = current / "__init__.py"
        if init_path.exists():
            continue
        _write_text(init_path, "")
        created.append(init_path)
    return created


def _ensure_package_root(root: Path) -> list[Path]:
    root.mkdir(parents=True, exist_ok=True)
    init_path = root / "__init__.py"
    if init_path.exists():
        return []
    _write_text(init_path, "")
    return [init_path]


def _prompt(label: str, *, default: str = "", input_fn: Callable[[str], str]) -> str:
    suffix = " [{default}]".format(default=default) if default else ""
    value = input_fn("{label}{suffix}: ".format(label=label, suffix=suffix))
    return value.strip()


def _prompt_required(label: str, *, input_fn: Callable[[str], str]) -> str:
    while True:
        value = _prompt(label, input_fn=input_fn)
        if value:
            return value


def _prompt_or_default(
    label: str, *, default: str, input_fn: Callable[[str], str]
) -> str:
    value = _prompt(label, default=default, input_fn=input_fn)
    return value or default


def _prompt_yes_no(
    label: str, *, default: bool, input_fn: Callable[[str], str]
) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        raw = (
            input_fn("{label} [{suffix}]: ".format(label=label, suffix=suffix))
            .strip()
            .lower()
        )
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False


def _prompt_choice(
    label: str,
    *,
    choices: Sequence[str],
    default: str,
    input_fn: Callable[[str], str],
) -> str:
    normalized_choices = tuple(
        choice.strip().lower() for choice in choices if choice.strip()
    )
    default_value = default.strip().lower()
    while True:
        raw = _prompt(
            label,
            default="/".join(
                "{item}{marker}".format(
                    item=item,
                    marker="*" if item == default_value else "",
                )
                for item in normalized_choices
            ),
            input_fn=input_fn,
        ).lower()
        if not raw:
            return default_value
        if raw in normalized_choices:
            return raw


def _prompt_multi_select(
    label: str,
    options: Sequence[str],
    *,
    default: Sequence[str],
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
) -> tuple[str, ...]:
    if not options:
        output_fn("{label}: no existing entries found.".format(label=label))
        return tuple(default)

    output_fn("{label}:".format(label=label))
    for index, option in enumerate(options, start=1):
        marker = " (default)" if option in default else ""
        output_fn(
            "  {index}. {option}{marker}".format(
                index=index, option=option, marker=marker
            )
        )

    default_text = ",".join(default)
    while True:
        raw = _prompt(
            "Select by number or name, comma-separated",
            default=default_text,
            input_fn=input_fn,
        )
        try:
            return _parse_multi_select(raw, options=options, default=default)
        except ValueError as exc:
            output_fn(str(exc))


def _parse_multi_select(
    raw: str, *, options: Sequence[str], default: Sequence[str]
) -> tuple[str, ...]:
    text = raw.strip()
    if not text:
        return tuple(default)

    option_by_name = {option.lower(): option for option in options}
    selected: list[str] = []
    seen: set[str] = set()
    for token in [item.strip() for item in text.split(",")]:
        if not token:
            continue
        choice: str | None = None
        if token.isdigit():
            index = int(token) - 1
            if index < 0 or index >= len(options):
                raise ValueError(
                    "Selection {token} is out of range. Choose values from 1 to {count}.".format(
                        token=token,
                        count=len(options),
                    )
                )
            choice = options[index]
        else:
            choice = option_by_name.get(token.lower())
            if choice is None:
                raise ValueError(
                    "Unknown selection: {token}. Use an item name or number from the list.".format(
                        token=token
                    )
                )
        if choice in seen:
            continue
        seen.add(choice)
        selected.append(choice)
    return tuple(selected)


def _build_system_prompt(plan: AgentScaffoldPlan) -> str:
    parts = [
        "You are the {name}.".format(name=plan.agent_name),
        _ensure_sentence(plan.responsibility),
        _STYLE_GUIDANCE[plan.answer_style],
        "Use skills when relevant, avoid inventing facts, and call tools only when they add material value.",
    ]
    if plan.tool_names:
        parts.append(
            "When a tool is available, prefer the smallest reliable sequence instead of over-calling tools."
        )
    else:
        parts.append(
            "If the answer would require unavailable data, say what is missing instead of guessing."
        )
    return " ".join(part.strip() for part in parts if part.strip())


def _format_string_expression(value: str, *, indent: str) -> str:
    wrapped = textwrap.wrap(value, width=84 - len(indent)) or [value]
    if len(wrapped) == 1:
        return '"{value}"'.format(value=_escape_python_string(wrapped[0]))
    lines = ["("]
    for index, line in enumerate(wrapped):
        suffix = " " if index < len(wrapped) - 1 else ""
        lines.append(
            '{indent}    "{line}{suffix}"'.format(
                indent=indent,
                line=_escape_python_string(line),
                suffix=suffix,
            )
        )
    lines.append("{indent})".format(indent=indent))
    return "\n".join(lines)


def _format_string_tuple(values: Sequence[str], *, indent: str) -> str:
    if not values:
        return "()"
    lines = ["("]
    for value in values:
        lines.append(
            '{indent}    "{value}",'.format(
                indent=indent,
                value=_escape_python_string(value),
            )
        )
    lines.append("{indent})".format(indent=indent))
    return "\n".join(lines)


def _normalize_identifier_segment(value: str, *, fallback: str) -> str:
    text = str(value or "").strip().lower()
    text = _NON_IDENTIFIER_RE.sub("_", text)
    text = text.strip("_")
    if not text:
        return fallback
    if text[0].isdigit():
        return "{fallback}_{text}".format(fallback=fallback, text=text)
    return text


def _escape_python_string(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace('"', '\\"')


def _pascal_case(value: str) -> str:
    parts = [part for part in _TITLE_SPLIT_RE.split(value) if part]
    name = "".join(part[:1].upper() + part[1:] for part in parts)
    if not name:
        return "Generated"
    if name[0].isdigit():
        return "Generated{value}".format(value=name)
    return name


def _titleize(value: str) -> str:
    parts = [part for part in _TITLE_SPLIT_RE.split(value.replace(".", " ")) if part]
    return " ".join(part[:1].upper() + part[1:] for part in parts) or "Generated"


def _merge_unique(existing: Sequence[str], new_items: Sequence[str]) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()
    for item in list(existing) + list(new_items):
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        merged.append(text)
    return tuple(merged)


def _ensure_sentence(value: str) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        return ""
    if text[-1] not in ".!?":
        return text + "."
    return text


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def main() -> int:
    workspace_root = SRC_DIR / "workspace"
    run_agent_scaffold_wizard(workspace_root, workspace_package="workspace")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
