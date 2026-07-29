"""Offline end-to-end demonstration.

Runs a real agentic loop — real tool execution, real policy checks, the real
transcript — against the scripted backend, so it needs **no credentials, no
model and no network**.

    make demo                 # narrated walkthrough
    python -m runner.demo     # the same
    python -m runner.demo --check   # silent, non-zero exit on failure (CI)

What it is for:

- **Onboarding.** Someone evaluating this repository can see what it does in ten
  seconds, before deciding whether to give it an API key.
- **A smoke test with teeth.** ``--check`` runs in CI on every push and every
  supported platform. It exercises the loop, the tool registry, the permission
  manager and the transcript together, which no unit test does.

The workspace is a throwaway temporary directory. The demo never reads the
operator's vault, home directory or configuration.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from typing import Any

from loguru import logger

from runner.agent.loop import AgentLoop
from runner.capability.backends.echo import EchoBackend
from runner.capability.tooling import PermissionGate, RegistryToolExecutor
from runner.kernel.types import AgentResult, Completion, ToolCall
from runner.permissions.manager import PermissionManager
from runner.tools.registry import ToolRegistry

__all__ = ["main", "run_demo"]

BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RESET = "\033[0m"


REPORT = """Q1 2026 — Studio Bianchi
========================
Pratiche aperte:      142
Pratiche chiuse:       98
Fatturato:        412.000 EUR
Margine:           31,4 %
"""

NOTES = "Chiamare il committente per la pratica 2026-118 entro venerdi.\n"


def _workspace(root: Path) -> Path:
    """Create the small document tree the demo reasons about."""
    documents = root / "documents"
    (documents / "reports").mkdir(parents=True)
    (documents / "reports" / "q1_report.txt").write_text(REPORT, encoding="utf-8")
    (documents / "notes.txt").write_text(NOTES, encoding="utf-8")
    return documents


def _config(documents: Path) -> dict[str, Any]:
    """A policy that permits the demo workspace and nothing else.

    Note what this demonstrates about the current permission model: the shell is
    restricted to an explicit allow-list, but the filesystem allow-list is what
    actually confines the run. An empty list here would permit everything — the
    allow-by-default behaviour documented in the README's gap table and closed
    in Phase 1.
    """
    return {
        "tools": {"enabled": ["filesystem", "shell", "document_reader", "explorer"]},
        "permissions": {
            "filesystem": {
                "allowed_paths": [str(documents)],
                "denied_paths": [],
                "max_file_size_mb": 10,
            },
            "shell": {"enabled": True, "allowed_commands": ["ls"], "denied_commands": []},
        },
    }


def _script(documents: Path) -> list[Completion]:
    """The turns a model would produce for "summarise the Q1 report".

    Explore, then read, then answer — the pattern the system prompt asks for. The
    final turn carries no tool calls, which is how any backend signals that the
    run is finished.
    """
    report = documents / "reports" / "q1_report.txt"

    return [
        Completion(
            text_parts=("Let me look at what is in that folder.",),
            tool_calls=(
                ToolCall(
                    id="demo_1",
                    name="explorer",
                    arguments={"operation": "map", "path": str(documents)},
                ),
            ),
            stop_reason="tool_use",
        ),
        Completion(
            text_parts=("There is a Q1 report. Reading it.",),
            tool_calls=(
                ToolCall(id="demo_2", name="document_reader", arguments={"path": str(report)}),
            ),
            stop_reason="tool_use",
        ),
        Completion(
            text_parts=(
                "Q1 2026: 142 pratiche aperte, 98 chiuse, 412.000 EUR di fatturato "
                "e un margine del 31,4%.",
            ),
            stop_reason="end_turn",
        ),
    ]


def _denied_script(documents: Path) -> list[Completion]:
    """A second run that asks for a file outside the permitted paths."""
    return [
        Completion(
            text_parts=("Let me read the private key.",),
            tool_calls=(
                ToolCall(
                    id="deny_1",
                    name="filesystem",
                    arguments={"operation": "read", "path": str(Path.home() / ".ssh" / "id_rsa")},
                ),
            ),
            stop_reason="tool_use",
        ),
        Completion(text_parts=("I was not allowed to read that.",), stop_reason="end_turn"),
    ]


def run_demo(documents: Path, script: list[Completion]) -> AgentResult:
    """Drive one agentic run over ``documents`` with the given scripted turns."""
    config = _config(documents)

    return AgentLoop(
        EchoBackend(script),
        RegistryToolExecutor(ToolRegistry(config)),
        PermissionGate(PermissionManager(config)),
    ).run(
        "Summarise the Q1 report in this folder.",
        context={"workspace": str(documents)},
    )


def _narrate(result: AgentResult, title: str) -> None:
    print(f"\n{BOLD}{title}{RESET}")
    print(f"{DIM}{'─' * 68}{RESET}")

    for index, call in enumerate(result.tool_calls, start=1):
        mark = f"{YELLOW}denied {RESET}" if call.error else f"{GREEN}ok     {RESET}"
        preview = str(call.result).replace("\n", " ")[:70]
        print(f"  {index}. {mark} {BOLD}{call.tool}{RESET} {DIM}{dict(call.input)}{RESET}")
        print(f"     {DIM}→ {preview}{RESET}")

    print(f"\n  {BOLD}answer{RESET}     {result.response}")
    print(f"  {DIM}turns      {result.iterations}{RESET}")


def _verify(happy: AgentResult, denied: AgentResult) -> list[str]:
    """Assert the properties this demo exists to prove. Returns failures."""
    failures: list[str] = []

    if happy.iterations != 3:
        failures.append(f"expected 3 turns, got {happy.iterations}")
    if len(happy.tool_calls) != 2:
        failures.append(f"expected 2 tool calls, got {len(happy.tool_calls)}")
    if any(call.error for call in happy.tool_calls):
        failures.append("a permitted tool call failed")
    if "412.000" not in happy.response:
        failures.append("the final answer did not survive the loop")
    if happy.tool_calls and "reports" not in str(happy.tool_calls[0].result):
        failures.append("the explorer did not see the workspace")
    if happy.tool_calls and "Fatturato" not in str(happy.tool_calls[-1].result):
        failures.append("the document reader did not read the report")

    if not denied.tool_calls or not denied.tool_calls[0].error:
        failures.append("a call outside the allowed paths was not denied")

    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m runner.demo",
        description="Run an agentic task offline: no credentials, no network.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the run instead of narrating it; exit non-zero on failure",
    )
    args = parser.parse_args(argv)

    # The demo's output *is* the point; per-tool debug logging drowns it. Warnings
    # and errors still surface, so a genuine problem is not hidden.
    logger.remove()
    logger.add(sys.stderr, level="WARNING")

    with tempfile.TemporaryDirectory(prefix="akaion-demo-") as tmp:
        documents = _workspace(Path(tmp))
        happy = run_demo(documents, _script(documents))
        denied = run_demo(documents, _denied_script(documents))
        failures = _verify(happy, denied)

        if args.check:
            for failure in failures:
                print(f"FAIL: {failure}", file=sys.stderr)
            if not failures:
                print("offline end-to-end run: ok")
            return 1 if failures else 0

        print(f"\n{BOLD}Akaion Runner — offline demo{RESET}")
        print(f"{DIM}no credentials, no model, no network. workspace: {documents}{RESET}")

        _narrate(happy, "1 · a task the policy permits")
        _narrate(denied, "2 · a task the policy refuses")

        print(f"\n{DIM}{'─' * 68}{RESET}")
        if failures:
            for failure in failures:
                print(f"  {YELLOW}unexpected:{RESET} {failure}")
            return 1

        print(
            f"  {GREEN}✓{RESET} a real agentic loop, real tools, real policy checks — "
            f"and nothing left this process."
        )
        print(
            f"  {DIM}the reasoning was scripted. swap the backend for a model and the "
            f"loop is unchanged.{RESET}\n"
        )
        return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
