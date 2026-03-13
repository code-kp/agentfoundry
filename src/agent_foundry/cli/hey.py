from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
STOP_RETRIES = 20
STOP_WAIT_SECONDS = 0.25
DEFAULT_RELOAD_EXCLUDES = (
    ".venv/*",
    "*/.venv/*",
    "venv/*",
    "*/venv/*",
    "*site-packages/*",
    "__pycache__/*",
)


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


@dataclass(frozen=True)
class CommandContext:
    config: HeyConfig
    extra_args: tuple[str, ...]


class CommandUsageError(RuntimeError):
    pass


class ProjectConfigLoader:
    def load(self, project_root: Path | None = None) -> HeyConfig:
        root = (project_root or Path.cwd()).resolve()
        pyproject_path = root / "pyproject.toml"
        if not pyproject_path.is_file():
            return HeyConfig()

        parsed = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        tool = parsed.get("tool", {})
        raw_config = tool.get("agentfoundry", {})
        if not isinstance(raw_config, dict):
            return HeyConfig()

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
            reload_dirs=self._normalize_str_list(
                raw_config.get("reload_dirs", HeyConfig.reload_dirs),
                fallback=HeyConfig.reload_dirs,
            ),
            test_paths=self._normalize_str_list(
                raw_config.get("test_paths", HeyConfig.test_paths),
                fallback=HeyConfig.test_paths,
            ),
            format_targets=self._normalize_str_list(
                raw_config.get("format_targets", HeyConfig.format_targets),
                fallback=HeyConfig.format_targets,
            ),
        )

    def _normalize_str_list(
        self,
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


class ProcessRunner:
    def run(self, command: Sequence[str]) -> int:
        return subprocess.call(list(command))


class UvicornCommandBuilder:
    def build(
        self,
        *,
        config: HeyConfig,
        host: str,
        port: int,
        app_path: str,
        reload: bool,
    ) -> list[str]:
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
        if not reload:
            return command

        for directory in config.reload_dirs:
            command.extend(["--reload-dir", directory])
        command.extend(["--reload", "--reload-include", "*.py"])
        for pattern in DEFAULT_RELOAD_EXCLUDES:
            command.extend(["--reload-exclude", pattern])
        return command


class AgentScaffoldService:
    def run(self, config: HeyConfig, extra_args: Sequence[str]) -> int:
        from agent_foundry.cli.new_agent import main as create_agent_main

        return create_agent_main(
            [
                "--workspace-root",
                config.workspace_root,
                "--workspace-package",
                config.workspace_package,
                *extra_args,
            ]
        )


class EmbeddingSyncService:
    def run(self, config: HeyConfig, extra_args: Sequence[str]) -> int:
        from agent_foundry.cli.sync_embeddings import main as sync_embeddings_main

        return sync_embeddings_main(
            [
                "--workspace-root",
                config.workspace_root,
                "--data-root",
                config.data_root,
                *extra_args,
            ]
        )


class PortProcessManager:
    def stop(self, port: int) -> int:
        pids = self._find_listening_pids(port)
        if not pids:
            print("[stop] No listening process found on port {port}.".format(port=port))
            return 0

        targets = self._expand_process_tree(pids)
        print(
            "[stop] Stopping processes on port {port}: {pids}".format(
                port=port,
                pids=", ".join(str(pid) for pid in sorted(targets)),
            )
        )
        denied = self._terminate_processes(targets, force=False)
        remaining = self._wait_for_exit(targets)
        if remaining:
            denied.extend(self._terminate_processes(remaining, force=True))
            remaining = self._wait_for_exit(remaining)

        if denied:
            print(
                "[stop] Could not signal processes due to permissions: {pids}".format(
                    pids=", ".join(str(pid) for pid in sorted(set(denied))),
                )
            )
        if remaining:
            print(
                "[stop] Some processes are still running: {pids}".format(
                    pids=", ".join(str(pid) for pid in sorted(remaining)),
                )
            )
            return 1
        if denied:
            return 1

        print("[stop] Port {port} is clear.".format(port=port))
        return 0

    def _find_listening_pids(self, port: int) -> list[int]:
        if os.name == "nt":
            return self._find_windows_listening_pids(port)
        return self._find_unix_listening_pids(port)

    def _expand_process_tree(self, pids: Sequence[int]) -> list[int]:
        seen: set[int] = set()
        ordered: list[int] = []
        pending = [pid for pid in pids if pid > 0]

        while pending:
            pid = pending.pop()
            if pid in seen:
                continue
            seen.add(pid)
            ordered.append(pid)
            pending.extend(self._child_pids(pid))

        return list(reversed(ordered))

    def _terminate_processes(self, pids: Sequence[int], *, force: bool) -> list[int]:
        denied: list[int] = []
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
            except PermissionError:
                denied.append(pid)
        return denied

    def _wait_for_exit(self, pids: Sequence[int]) -> list[int]:
        remaining = [pid for pid in pids if self._pid_running(pid)]
        for _ in range(STOP_RETRIES):
            if not remaining:
                return []
            time.sleep(STOP_WAIT_SECONDS)
            remaining = [pid for pid in remaining if self._pid_running(pid)]
        return remaining

    def _find_unix_listening_pids(self, port: int) -> list[int]:
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

        pids: list[int] = []
        for raw_line in result.stdout.splitlines():
            value = raw_line.strip()
            if value.isdigit():
                pids.append(int(value))
        return sorted(set(pids))

    def _find_windows_listening_pids(self, port: int) -> list[int]:
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

        pids: list[int] = []
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

    def _child_pids(self, pid: int) -> list[int]:
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

        children: list[int] = []
        for raw_line in result.stdout.splitlines():
            value = raw_line.strip()
            if value.isdigit():
                children.append(int(value))
        return children

    def _pid_running(self, pid: int) -> bool:
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


class HeyCommand(ABC):
    name: str
    help: str
    aliases: tuple[str, ...] = ()

    def register(self, subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
        parser = subparsers.add_parser(
            self.name,
            aliases=list(self.aliases),
            help=self.help,
        )
        self.configure(parser)

    def configure(self, parser: argparse.ArgumentParser) -> None:
        return None

    @abstractmethod
    def execute(self, args: argparse.Namespace, context: CommandContext) -> int:
        raise NotImplementedError


class StartCommand(HeyCommand):
    name = "start"
    aliases = ("dev",)
    help = "Start the local app with Uvicorn reload enabled."

    def __init__(
        self,
        *,
        runner: ProcessRunner,
        builder: UvicornCommandBuilder,
    ) -> None:
        self._runner = runner
        self._builder = builder

    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--host", default="")
        parser.add_argument("--port", type=int, default=0)
        parser.add_argument("--app", default="")
        parser.add_argument(
            "--no-reload",
            action="store_true",
            help="Disable Uvicorn reload for one-off runs.",
        )

    def execute(self, args: argparse.Namespace, context: CommandContext) -> int:
        ensure_no_extra_args(self.name, context.extra_args)
        command = self._builder.build(
            config=context.config,
            host=args.host or context.config.host,
            port=int(args.port or context.config.port),
            app_path=args.app or context.config.app,
            reload=not args.no_reload,
        )
        return self._runner.run(command)


class StopCommand(HeyCommand):
    name = "stop"
    help = "Stop the process currently listening on the configured app port."

    def __init__(self, *, manager: PortProcessManager) -> None:
        self._manager = manager

    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--port", type=int, default=0)

    def execute(self, args: argparse.Namespace, context: CommandContext) -> int:
        ensure_no_extra_args(self.name, context.extra_args)
        return self._manager.stop(int(args.port or context.config.port))


class CreateAgentCommand(HeyCommand):
    name = "create-agent"
    aliases = ("new-agent",)
    help = "Run the shared agent scaffold wizard against the current workspace."

    def __init__(self, *, scaffold_service: AgentScaffoldService) -> None:
        self._scaffold_service = scaffold_service

    def execute(self, args: argparse.Namespace, context: CommandContext) -> int:
        del args
        return self._scaffold_service.run(context.config, context.extra_args)


class SyncEmbeddingCommand(HeyCommand):
    name = "sync-embedding"
    aliases = ("sync-embeddings",)
    help = "Refresh semantic retrieval embeddings for the current workspace."

    def __init__(self, *, sync_service: EmbeddingSyncService) -> None:
        self._sync_service = sync_service

    def execute(self, args: argparse.Namespace, context: CommandContext) -> int:
        del args
        return self._sync_service.run(context.config, context.extra_args)


class FormatCommand(HeyCommand):
    name = "format"
    help = "Run ruff format against the current project."

    def __init__(self, *, runner: ProcessRunner) -> None:
        self._runner = runner

    def execute(self, args: argparse.Namespace, context: CommandContext) -> int:
        del args
        command = [
            sys.executable,
            "-m",
            "ruff",
            "format",
            *context.config.format_targets,
            *context.extra_args,
        ]
        return self._runner.run(command)


class TestCommand(HeyCommand):
    name = "test"
    help = "Run pytest for the current project."

    def __init__(self, *, runner: ProcessRunner) -> None:
        self._runner = runner

    def execute(self, args: argparse.Namespace, context: CommandContext) -> int:
        del args
        command = [
            sys.executable,
            "-m",
            "pytest",
            *context.config.test_paths,
            *context.extra_args,
        ]
        return self._runner.run(command)


class HeyApplication:
    def __init__(
        self,
        *,
        config_loader: ProjectConfigLoader,
        commands: Sequence[HeyCommand],
    ) -> None:
        self._config_loader = config_loader
        self._commands_by_name: dict[str, HeyCommand] = {}
        self._parser = argparse.ArgumentParser(
            description="Shared AgentFoundry project CLI."
        )
        subparsers = self._parser.add_subparsers(dest="command", required=True)
        for command in commands:
            command.register(subparsers)
            self._commands_by_name[command.name] = command
            for alias in command.aliases:
                self._commands_by_name[alias] = command

    def run(self, argv: list[str] | None = None) -> int:
        args, extra_args = self._parser.parse_known_args(argv)
        command = self._commands_by_name[str(args.command or "")]
        context = CommandContext(
            config=self._config_loader.load(),
            extra_args=tuple(extra_args),
        )
        try:
            return command.execute(args, context)
        except CommandUsageError as exc:
            print(exc, file=sys.stderr)
            return 2


def build_default_app() -> HeyApplication:
    runner = ProcessRunner()
    return HeyApplication(
        config_loader=ProjectConfigLoader(),
        commands=(
            StartCommand(runner=runner, builder=UvicornCommandBuilder()),
            StopCommand(manager=PortProcessManager()),
            CreateAgentCommand(scaffold_service=AgentScaffoldService()),
            SyncEmbeddingCommand(sync_service=EmbeddingSyncService()),
            FormatCommand(runner=runner),
            TestCommand(runner=runner),
        ),
    )


def ensure_no_extra_args(command_name: str, extra_args: Sequence[str]) -> None:
    if not extra_args:
        return
    raise CommandUsageError(
        "Unexpected extra arguments for `hey {command}`: {args}".format(
            command=command_name,
            args=" ".join(extra_args),
        )
    )


def main(argv: list[str] | None = None) -> int:
    return build_default_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
