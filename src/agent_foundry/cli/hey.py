from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from agent_foundry.cli.new_agent import main as create_agent_main
from agent_foundry.cli.sync_embeddings import main as sync_embeddings_main

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
STOP_RETRIES = 20
STOP_WAIT_SECONDS = 0.25


@dataclass(frozen=True)
class HeyConfig:
    app: str = "foundry_app.app:app"
    app_dir: str = "src"
    workspace_root: str = "src/workspace"
    workspace_package: str = "workspace"
    data_root: str = "."
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    reload_dirs: tuple[str, ...] = ("src", "tests")
    test_paths: tuple[str, ...] = ("tests",)
    format_targets: tuple[str, ...] = (".",)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Shared AgentFoundry project CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser(
        "start",
        aliases=["dev"],
        help="Start the local app with Uvicorn reload enabled.",
    )
    start_parser.add_argument("--host", default="")
    start_parser.add_argument("--port", type=int, default=0)
    start_parser.add_argument("--app", default="")
    start_parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Disable Uvicorn reload for one-off runs.",
    )

    stop_parser = subparsers.add_parser(
        "stop",
        help="Stop the process currently listening on the configured app port.",
    )
    stop_parser.add_argument("--port", type=int, default=0)

    create_agent_parser = subparsers.add_parser(
        "create-agent",
        aliases=["new-agent"],
        help="Run the shared agent scaffold wizard against the current workspace.",
    )

    sync_parser = subparsers.add_parser(
        "sync-embedding",
        aliases=["sync-embeddings"],
        help="Refresh semantic retrieval embeddings for the current workspace.",
    )

    format_parser = subparsers.add_parser(
        "format",
        help="Run ruff format against the current project.",
    )

    test_parser = subparsers.add_parser(
        "test",
        help="Run pytest for the current project.",
    )

    args, extra_args = parser.parse_known_args(argv)
    config = load_config()
    command = str(args.command or "")
    if command in {"start", "dev"}:
        return start_app(
            config=config,
            host=args.host or config.host,
            port=int(args.port or config.port),
            app_path=args.app or config.app,
            reload=not args.no_reload,
        )
    if command == "stop":
        return stop_port(int(args.port or config.port))
    if command in {"create-agent", "new-agent"}:
        return run_create_agent(config, extra_args)
    if command in {"sync-embedding", "sync-embeddings"}:
        return run_sync_embeddings(config, extra_args)
    if command == "format":
        return run_format(config, extra_args)
    if command == "test":
        return run_test(config, extra_args)
    return 1


def load_config(project_root: Path | None = None) -> HeyConfig:
    root = (project_root or Path.cwd()).resolve()
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.is_file():
        return HeyConfig()

    parsed = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    tool = parsed.get("tool", {})
    raw_config = tool.get("agentfoundry", {})
    if not isinstance(raw_config, dict):
        return HeyConfig()

    normalized_reload_dirs = _normalize_str_list(
        raw_config.get("reload_dirs", HeyConfig.reload_dirs),
        fallback=HeyConfig.reload_dirs,
    )
    normalized_test_paths = _normalize_str_list(
        raw_config.get("test_paths", HeyConfig.test_paths),
        fallback=HeyConfig.test_paths,
    )
    normalized_format_targets = _normalize_str_list(
        raw_config.get("format_targets", HeyConfig.format_targets),
        fallback=HeyConfig.format_targets,
    )

    return HeyConfig(
        app=str(raw_config.get("app", HeyConfig.app)).strip() or HeyConfig.app,
        app_dir=(
            str(raw_config.get("app_dir", HeyConfig.app_dir)).strip()
            or HeyConfig.app_dir
        ),
        workspace_root=(
            str(raw_config.get("workspace_root", HeyConfig.workspace_root)).strip()
            or HeyConfig.workspace_root
        ),
        workspace_package=(
            str(
                raw_config.get("workspace_package", HeyConfig.workspace_package)
            ).strip()
            or HeyConfig.workspace_package
        ),
        data_root=(
            str(raw_config.get("data_root", HeyConfig.data_root)).strip()
            or HeyConfig.data_root
        ),
        host=str(raw_config.get("host", HeyConfig.host)).strip() or HeyConfig.host,
        port=int(raw_config.get("port", HeyConfig.port)),
        reload_dirs=normalized_reload_dirs,
        test_paths=normalized_test_paths,
        format_targets=normalized_format_targets,
    )


def start_app(
    *,
    config: HeyConfig,
    host: str,
    port: int,
    app_path: str,
    reload: bool,
) -> int:
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        app_path,
        "--app-dir",
        config.app_dir,
        "--host",
        host,
        "--port",
        str(port),
    ]
    if reload:
        for directory in config.reload_dirs:
            command.extend(["--reload-dir", directory])
        command.extend(
            [
                "--reload",
                "--reload-include",
                "*.py",
                "--reload-exclude",
                ".venv/*",
                "--reload-exclude",
                "*/.venv/*",
                "--reload-exclude",
                "venv/*",
                "--reload-exclude",
                "*/venv/*",
                "--reload-exclude",
                "*site-packages/*",
                "--reload-exclude",
                "__pycache__/*",
            ]
        )
    return subprocess.call(command)


def run_create_agent(config: HeyConfig, extra_args: list[str]) -> int:
    return create_agent_main(
        [
            "--workspace-root",
            config.workspace_root,
            "--workspace-package",
            config.workspace_package,
            *extra_args,
        ]
    )


def run_sync_embeddings(config: HeyConfig, extra_args: list[str]) -> int:
    return sync_embeddings_main(
        [
            "--workspace-root",
            config.workspace_root,
            "--data-root",
            config.data_root,
            *extra_args,
        ]
    )


def run_format(config: HeyConfig, extra_args: list[str]) -> int:
    command = [
        sys.executable,
        "-m",
        "ruff",
        "format",
        *config.format_targets,
        *extra_args,
    ]
    return subprocess.call(command)


def run_test(config: HeyConfig, extra_args: list[str]) -> int:
    command = [
        sys.executable,
        "-m",
        "pytest",
        *config.test_paths,
        *extra_args,
    ]
    return subprocess.call(command)


def stop_port(port: int) -> int:
    pids = find_listening_pids(port)
    if not pids:
        print("[stop] No listening process found on port {port}.".format(port=port))
        return 0

    targets = expand_process_tree(pids)
    print(
        "[stop] Stopping processes on port {port}: {pids}".format(
            port=port,
            pids=", ".join(str(pid) for pid in sorted(targets)),
        )
    )
    terminate_processes(targets, force=False)
    remaining = wait_for_exit(targets)
    if remaining:
        terminate_processes(remaining, force=True)
        remaining = wait_for_exit(remaining)

    if remaining:
        print(
            "[stop] Some processes are still running: {pids}".format(
                pids=", ".join(str(pid) for pid in sorted(remaining))
            )
        )
        return 1

    print("[stop] Port {port} is clear.".format(port=port))
    return 0


def find_listening_pids(port: int) -> list[int]:
    if os.name == "nt":
        return _find_windows_listening_pids(port)
    return _find_unix_listening_pids(port)


def expand_process_tree(pids: list[int]) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []
    pending = [pid for pid in pids if pid > 0]

    while pending:
        pid = pending.pop()
        if pid in seen:
            continue
        seen.add(pid)
        ordered.append(pid)
        pending.extend(_child_pids(pid))

    return list(reversed(ordered))


def terminate_processes(pids: list[int], *, force: bool) -> None:
    for pid in pids:
        if os.name == "nt":
            command = ["taskkill", "/PID", str(pid), "/T"]
            if force:
                command.append("/F")
            subprocess.run(command, capture_output=True, text=True, check=False)
            continue

        try:
            os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
        except ProcessLookupError:
            continue


def wait_for_exit(pids: list[int]) -> list[int]:
    remaining = [pid for pid in pids if _pid_running(pid)]
    for _ in range(STOP_RETRIES):
        if not remaining:
            return []
        time.sleep(STOP_WAIT_SECONDS)
        remaining = [pid for pid in remaining if _pid_running(pid)]
    return remaining


def _find_unix_listening_pids(port: int) -> list[int]:
    result = subprocess.run(
        ["lsof", "-nP", "-tiTCP:{port}".format(port=port), "-sTCP:LISTEN"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(
            result.stderr.strip() or "Failed to inspect listening ports."
        )

    pids = []
    for raw_line in result.stdout.splitlines():
        value = raw_line.strip()
        if value.isdigit():
            pids.append(int(value))
    return sorted(set(pids))


def _normalize_str_list(
    raw_value: object,
    *,
    fallback: tuple[str, ...],
) -> tuple[str, ...]:
    if isinstance(raw_value, str):
        raw_items = (raw_value,)
    elif isinstance(raw_value, (list, tuple)):
        raw_items = raw_value
    else:
        return fallback

    normalized = tuple(str(item).strip() for item in raw_items if str(item).strip())
    return normalized or fallback


def _find_windows_listening_pids(port: int) -> list[int]:
    result = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip() or "Failed to inspect listening ports."
        )

    pids = []
    needle = ":{port}".format(port=port)
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if "LISTENING" not in line:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        local_address = parts[1]
        pid = parts[-1]
        if not local_address.endswith(needle):
            continue
        if pid.isdigit():
            pids.append(int(pid))
    return sorted(set(pids))


def _child_pids(pid: int) -> list[int]:
    if os.name == "nt":
        return []

    result = subprocess.run(
        ["pgrep", "-P", str(pid)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        return []

    children = []
    for raw_line in result.stdout.splitlines():
        value = raw_line.strip()
        if value.isdigit():
            children.append(int(value))
    return children


def _pid_running(pid: int) -> bool:
    if pid <= 0:
        return False

    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", "PID eq {pid}".format(pid=pid)],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in result.stdout

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


if __name__ == "__main__":
    raise SystemExit(main())
