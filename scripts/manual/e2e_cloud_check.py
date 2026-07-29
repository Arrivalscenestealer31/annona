#!/usr/bin/env python3
"""
End-to-End test for Akaion Runner against the cloud backend.

Usage:
    python test_e2e.py --token <firebase_token> [--path <dir_to_explore>]

The script:
  1. Verifies cloud connectivity (health check)
  2. Registers the runner
  3. Runs a REAL agentic task (explore a local directory) using /runner/agent/turn
  4. Falls back to the legacy /kai/runner/execute if the new endpoint is not deployed
  5. Submits the result back to the cloud
"""
import sys
import os
import json
import time
import uuid
import argparse
import platform
import tempfile
from pathlib import Path

import httpx
from loguru import logger

# ── Add runner to path ────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from runner.tools.registry import ToolRegistry
from runner.tools.filesystem import FilesystemTool
from runner.tools.explorer import ExplorerTool
from runner.tools.document_reader import DocumentReaderTool
from runner.tools.shell import ShellTool
from runner.permissions.manager import PermissionManager

# ── Config ────────────────────────────────────────────────────────────────────
# Cloud:  https://api.prod.akaion.com/api/service4
# Local:  http://localhost:8084
AI_BACKEND_URL = "https://api.prod.akaion.com/api/service4"

RUNNER_CONFIG = {
    "tools": {
        "enabled": ["filesystem", "shell", "document_reader", "explorer"]
    },
    "permissions": {
        "filesystem": {
            "allowed_paths": [],   # empty = unrestricted
            "denied_paths": [str(Path.home() / ".ssh")],
            "max_file_size_mb": 50,
        },
        "shell": {
            "enabled": True,
            "allowed_commands": [],
            "denied_commands": ["rm -rf /", "sudo rm"],
        },
    },
}

# ─────────────────────────────────────────────────────────────────────────────


class E2ERunner:
    def __init__(self, token: str, explore_path: str, backend_url: str = AI_BACKEND_URL):
        self.token = token
        self.explore_path = Path(explore_path).expanduser().resolve()
        self.runner_id = str(uuid.uuid4())
        self.machine_id = platform.node()
        self.backend_url = backend_url

        self.client = httpx.Client(
            base_url=backend_url,
            timeout=60,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-Runner-ID": self.runner_id,
            },
        )

        self.tools = ToolRegistry(RUNNER_CONFIG)
        self.perms = PermissionManager(RUNNER_CONFIG)

        # Tool schemas for the backend
        self.tool_schemas = [
            {
                "name": s["name"],
                "description": s["description"],
                "input_schema": s["parameters"],
            }
            for s in self.tools.get_all_schemas()
        ]

    # ── Step 1: Health check ──────────────────────────────────────────────────

    def check_health(self) -> bool:
        logger.info("Step 1 — Health check...")
        try:
            r = self.client.get("/api/v1/kai/health")
            if r.status_code == 200:
                logger.success(f"  Backend healthy: {r.json()}")
                return True
            logger.warning(f"  Health check returned {r.status_code}: {r.text[:200]}")
            return False
        except Exception as e:
            logger.error(f"  Health check failed: {e}")
            return False

    # ── Step 2: Register runner ───────────────────────────────────────────────

    def register(self) -> bool:
        logger.info("Step 2 — Registering runner...")
        try:
            r = self.client.post(
                "/api/v1/runner/register",
                json={
                    "runner_name": f"e2e-test-{self.machine_id}",
                    "machine_id": self.machine_id,
                    "capabilities": ["filesystem", "shell", "document_reader", "explorer"],
                    "system_info": {
                        "os": platform.system(),
                        "os_version": platform.version(),
                        "python": platform.python_version(),
                        "machine": self.machine_id,
                    },
                    "callback_url": "http://localhost:9999/callback",  # not used in E2E
                },
            )
            if r.status_code == 200:
                data = r.json()
                logger.success(f"  Runner registered: {data.get('runner_id')}")
                logger.info(f"  Polling URL: {data.get('polling_url')}")
                # Use the server-assigned runner_id
                self.runner_id = data.get("runner_id", self.runner_id)
                self.client.headers["X-Runner-ID"] = self.runner_id
                return True
            else:
                logger.warning(f"  Registration returned {r.status_code}: {r.text[:300]}")
                logger.info("  Continuing with generated runner_id (endpoint may need deployment)")
                return True  # Non-blocking: continue anyway
        except Exception as e:
            logger.error(f"  Registration error: {e}")
            return True  # Non-blocking

    # ── Step 3: Agentic loop via /runner/agent/turn ───────────────────────────

    def run_agent_turn(
        self, messages: list, system_prompt: str
    ) -> dict | None:
        """Call the backend for one agent turn."""
        r = self.client.post(
            "/api/v1/runner/agent/turn",
            json={
                "runner_id": self.runner_id,
                "messages": messages,
                "tools": self.tool_schemas,
                "system_prompt": system_prompt,
                "temperature": 0.3,
                "max_tokens": 4096,
            },
        )
        if r.status_code == 200:
            return r.json()
        logger.error(f"  /agent/turn error {r.status_code}: {r.text[:400]}")
        return None

    def run_agentic_task(self, prompt: str, max_iter: int = 8) -> dict:
        """Full agentic loop: send → tool_use → execute locally → repeat."""
        system_prompt = (
            "You are an advanced local agent running on the user's machine. "
            "You have access to tools to explore the filesystem, read documents of any format "
            "(PDF, DOCX, XLSX, CSV, code files), execute shell commands, and analyse content. "
            "Be thorough: always explore structure first, then read relevant files, "
            "then produce a clear report. "
            f"Working path: {self.explore_path}"
        )

        messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}],
            }
        ]

        tool_calls = []
        final_response = ""

        for i in range(max_iter):
            logger.info(f"  Iteration {i+1}/{max_iter} — calling backend...")
            turn = self.run_agent_turn(messages, system_prompt)

            if not turn:
                logger.error("  Backend returned None — aborting")
                break

            stop_reason = turn.get("stop_reason", "end_turn")
            content = turn.get("content", [])
            tokens = turn.get("tokens_used", 0)
            model = turn.get("model", "unknown")

            logger.info(f"  stop_reason={stop_reason}  tokens={tokens}  model={model}")

            tool_use_blocks = []
            for block in content:
                if block.get("type") == "text":
                    final_response = block.get("text", "")
                    logger.info(f"  AI text: {final_response[:120]}{'...' if len(final_response) > 120 else ''}")
                elif block.get("type") == "tool_use":
                    tool_use_blocks.append(block)

            if stop_reason == "end_turn" or not tool_use_blocks:
                logger.success(f"  Done after {i+1} iterations")
                break

            # Execute tools locally
            tool_results = []
            for tu in tool_use_blocks:
                tool_name = tu.get("name")
                tool_input = tu.get("input") or {}
                tu_id = tu.get("id")

                logger.info(f"  Executing tool: {tool_name}({json.dumps(tool_input)[:80]})")

                if not self.perms.check_tool_permission(tool_name, tool_input):
                    result = {"error": f"Permission denied: {tool_name}"}
                    is_error = True
                else:
                    try:
                        tool_obj = self.tools.get_tool(tool_name)
                        result = tool_obj.execute(**tool_input)
                        is_error = False
                        logger.success(f"  Tool OK: {str(result)[:100]}...")
                    except Exception as e:
                        result = {"error": str(e)}
                        is_error = True
                        logger.error(f"  Tool error: {e}")

                tool_calls.append({
                    "tool": tool_name,
                    "input": tool_input,
                    "result": result,
                    "error": is_error,
                })

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu_id,
                    "content": json.dumps(result),
                    "is_error": is_error,
                })

            # Append assistant turn + tool results
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": tool_results})

        return {
            "response": final_response,
            "tool_calls": tool_calls,
            "iterations": i + 1,
        }

    # ── Step 3b: Legacy fallback ──────────────────────────────────────────────

    def run_legacy_execute(self, prompt: str) -> dict:
        """Fallback to the existing /kai/runner/execute (one-shot, no tool loop)."""
        logger.warning("  Falling back to legacy /kai/runner/execute (one-shot)...")
        r = self.client.post(
            "/api/v1/kai/runner/execute",
            json={
                "command": prompt,
                "runner_id": self.runner_id,
                "working_directory": str(self.explore_path),
                "available_tools": ["filesystem", "shell", "explorer", "document_reader"],
                "temperature": 0.5,
                "max_tokens": 2000,
            },
        )
        if r.status_code == 200:
            return r.json()
        logger.error(f"  Legacy execute error {r.status_code}: {r.text[:400]}")
        return {}

    # ── Step 4: Submit result ─────────────────────────────────────────────────

    def submit_result(self, task_id: str, output: str, success: bool):
        logger.info("Step 4 — Submitting result to cloud...")
        try:
            r = self.client.post(
                "/api/v1/runner/tasks/result",
                json={
                    "task_id": task_id,
                    "success": success,
                    "output": output[:4000],
                    "execution_time": 0.0,
                },
            )
            if r.status_code == 200:
                logger.success(f"  Result submitted: {r.json()}")
            else:
                logger.warning(f"  Submit returned {r.status_code}: {r.text[:200]}")
        except Exception as e:
            logger.error(f"  Submit error: {e}")

    # ── Main flow ─────────────────────────────────────────────────────────────

    def run(self):
        logger.info("=" * 60)
        logger.info("Akaion Runner — End-to-End Test")
        logger.info(f"Backend: {self.backend_url}")
        logger.info(f"Explore: {self.explore_path}")
        logger.info("=" * 60)

        # 1. Health
        self.check_health()

        # 2. Register
        self.register()

        # 3. Run task
        prompt = (
            f"Analyze the directory {self.explore_path}:\n"
            "1. Map the full directory tree\n"
            "2. List all files grouped by type\n"
            "3. Read the content of the most relevant documents you find\n"
            "4. Produce a concise report: folder structure, file inventory, and key content summary"
        )

        logger.info("=" * 60)
        logger.info(f"Step 3 — Running agentic task...")
        logger.info(f"Prompt: {prompt[:120]}...")
        logger.info("=" * 60)

        start = time.time()

        # Try new /agent/turn endpoint first
        try:
            probe = self.client.get("/api/v1/runner/agent/turn")
            endpoint_exists = probe.status_code != 404
        except Exception:
            endpoint_exists = False

        # Always try the agentic loop first
        result = self.run_agentic_task(prompt)

        # If we got nothing useful, try legacy
        if not result.get("response") and not result.get("tool_calls"):
            legacy = self.run_legacy_execute(prompt)
            result = {
                "response": legacy.get("response", ""),
                "tool_calls": [],
                "iterations": 1,
                "legacy": True,
            }

        elapsed = time.time() - start

        # 4. Submit (using a fake task_id for E2E)
        fake_task_id = f"e2e-{int(time.time())}"
        self.submit_result(fake_task_id, result.get("response", ""), True)

        # ── Print final report ─────────────────────────────────────────────────
        logger.info("")
        logger.info("=" * 60)
        logger.info("E2E TEST RESULTS")
        logger.info("=" * 60)
        logger.info(f"Duration:    {elapsed:.1f}s")
        logger.info(f"Iterations:  {result.get('iterations', 0)}")
        logger.info(f"Tool calls:  {len(result.get('tool_calls', []))}")
        logger.info(f"Mode:        {'legacy' if result.get('legacy') else 'agentic'}")
        logger.info("")
        logger.info("Tool call log:")
        for tc in result.get("tool_calls", []):
            status = "✓" if not tc["error"] else "✗"
            r = tc["result"]
            summary = (
                f"success={r.get('success')}" if isinstance(r, dict) and "success" in r
                else str(r)[:60]
            )
            logger.info(f"  {status} {tc['tool']}({json.dumps(tc['input'])[:50]}) → {summary}")

        logger.info("")
        logger.info("Final AI response:")
        logger.info("-" * 40)
        print(result.get("response", "(empty)"))
        logger.info("-" * 40)

        return result


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Akaion Runner E2E Test")
    parser.add_argument(
        "--token", required=True,
        help="Firebase ID token (Bearer)"
    )
    parser.add_argument(
        "--path", default=str(Path.home() / "Desktop"),
        help="Local directory to explore (default: ~/Desktop)"
    )
    parser.add_argument(
        "--backend-url", default=AI_BACKEND_URL,
        help=f"AI backend base URL (default: {AI_BACKEND_URL}; use http://localhost:8084 for local)"
    )
    args = parser.parse_args()

    runner = E2ERunner(token=args.token, explore_path=args.path, backend_url=args.backend_url)
    runner.run()


if __name__ == "__main__":
    main()
