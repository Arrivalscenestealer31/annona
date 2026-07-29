"""
Tests for the agentic loop in AIClient.reason_and_execute.

Uses Anthropic's native tool-use loop.
All LLM calls are mocked — no network required.
"""

from unittest.mock import MagicMock, patch

from runner.ai_client import AIClient
from runner.permissions.manager import PermissionManager
from runner.tools.registry import ToolRegistry

# ── Fixtures ──────────────────────────────────────────────────────────────────

ANTHROPIC_CONFIG = {
    "ai": {
        "provider": "anthropic",
        "model": "claude-opus-4-6",
        "temperature": 0.3,
        "max_tokens": 2000,
        "anthropic": {"api_key": "sk-ant-test-fake-key"},  # bypasses env-var check
    },
    "tools": {"enabled": ["filesystem", "shell", "document_reader", "explorer"]},
    "permissions": {
        "filesystem": {"allowed_paths": [], "denied_paths": [], "max_file_size_mb": 50},
        "shell": {"enabled": True, "allowed_commands": [], "denied_commands": []},
    },
}


def make_anthropic_client(mock_anthropic_client):
    """Build AIClient with Anthropic provider, injecting mock."""
    with patch("anthropic.Anthropic", return_value=mock_anthropic_client):
        return AIClient(ANTHROPIC_CONFIG)


def _make_text_block(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _make_tool_use_block(tool_id: str, name: str, input_data: dict):
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = name
    block.input = input_data
    return block


def _make_response(blocks, stop_reason="end_turn"):
    resp = MagicMock()
    resp.content = blocks
    resp.stop_reason = stop_reason
    return resp


# ── Direct end_turn (no tools) ────────────────────────────────────────────────


class TestDirectResponse:
    def test_direct_text_response(self, tmp_path):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_response(
            [_make_text_block("The answer is 42.")]
        )

        with patch("anthropic.Anthropic", return_value=mock_client):
            ai = AIClient(ANTHROPIC_CONFIG)

        tools = ToolRegistry(ANTHROPIC_CONFIG)
        perms = PermissionManager(ANTHROPIC_CONFIG)

        result = ai.reason_and_execute("What is the answer?", {}, tools, perms)

        assert result["response"] == "The answer is 42."
        assert result["iterations"] == 1
        assert result["tool_calls"] == []

    def test_empty_content_handled(self, tmp_path):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_response([])

        with patch("anthropic.Anthropic", return_value=mock_client):
            ai = AIClient(ANTHROPIC_CONFIG)

        tools = ToolRegistry(ANTHROPIC_CONFIG)
        perms = PermissionManager(ANTHROPIC_CONFIG)

        result = ai.reason_and_execute("ping", {}, tools, perms)
        assert result["response"] == ""
        assert result["iterations"] == 1


# ── Single tool call ──────────────────────────────────────────────────────────


class TestSingleToolCall:
    def test_calls_filesystem_list(self, tmp_path):
        # Step 1: AI asks to list a directory
        # Step 2: result sent back → AI says end_turn
        (tmp_path / "notes.txt").write_text("hello")

        tool_block = _make_tool_use_block(
            "tu_1", "filesystem", {"operation": "list", "path": str(tmp_path)}
        )
        first_response = _make_response([tool_block], stop_reason="tool_use")
        second_response = _make_response([_make_text_block(f"Found notes.txt in {tmp_path}")])

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [first_response, second_response]

        with patch("anthropic.Anthropic", return_value=mock_client):
            ai = AIClient(ANTHROPIC_CONFIG)

        tools = ToolRegistry(ANTHROPIC_CONFIG)
        perms = PermissionManager(ANTHROPIC_CONFIG)

        result = ai.reason_and_execute(f"List files in {tmp_path}", {}, tools, perms)

        assert result["iterations"] == 2
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["tool"] == "filesystem"
        assert result["tool_calls"][0]["error"] is False
        assert "notes.txt" in str(result["tool_calls"][0]["result"])

    def test_calls_shell_tool(self, tmp_path):
        tool_block = _make_tool_use_block("tu_2", "shell", {"command": "echo hello"})
        first_response = _make_response([tool_block], stop_reason="tool_use")
        second_response = _make_response([_make_text_block("Shell said hello")])

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [first_response, second_response]

        with patch("anthropic.Anthropic", return_value=mock_client):
            ai = AIClient(ANTHROPIC_CONFIG)

        tools = ToolRegistry(ANTHROPIC_CONFIG)
        perms = PermissionManager(ANTHROPIC_CONFIG)

        result = ai.reason_and_execute("Run echo hello", {}, tools, perms)

        assert len(result["tool_calls"]) == 1
        tc = result["tool_calls"][0]
        assert tc["tool"] == "shell"
        assert tc["result"]["stdout"].strip() == "hello"

    def test_calls_explorer_map(self, sample_dir):
        tool_block = _make_tool_use_block(
            "tu_3", "explorer", {"operation": "map", "path": str(sample_dir)}
        )
        first_response = _make_response([tool_block], stop_reason="tool_use")
        second_response = _make_response([_make_text_block("Directory mapped.")])

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [first_response, second_response]

        with patch("anthropic.Anthropic", return_value=mock_client):
            ai = AIClient(ANTHROPIC_CONFIG)

        tools = ToolRegistry(ANTHROPIC_CONFIG)
        perms = PermissionManager(ANTHROPIC_CONFIG)

        result = ai.reason_and_execute(f"Map {sample_dir}", {}, tools, perms)

        assert len(result["tool_calls"]) == 1
        tc = result["tool_calls"][0]
        assert tc["tool"] == "explorer"
        assert tc["result"]["success"] is True
        assert "reports" in tc["result"]["tree"]

    def test_calls_document_reader(self, tmp_path):
        f = tmp_path / "report.txt"
        f.write_text("Revenue: 5,000,000\nProfit: 1,200,000\n")

        tool_block = _make_tool_use_block("tu_4", "document_reader", {"path": str(f)})
        first_response = _make_response([tool_block], stop_reason="tool_use")
        second_response = _make_response([_make_text_block("The report shows revenue of 5M.")])

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [first_response, second_response]

        with patch("anthropic.Anthropic", return_value=mock_client):
            ai = AIClient(ANTHROPIC_CONFIG)

        tools = ToolRegistry(ANTHROPIC_CONFIG)
        perms = PermissionManager(ANTHROPIC_CONFIG)

        result = ai.reason_and_execute(f"Read {f}", {}, tools, perms)

        assert (
            result["tool_calls"][0]["result"]["content"]
            == "Revenue: 5,000,000\nProfit: 1,200,000\n"
        )
        assert result["response"] == "The report shows revenue of 5M."


# ── Multi-step chain ──────────────────────────────────────────────────────────


class TestMultiStepChain:
    def test_explore_then_read_chain(self, sample_dir):
        """
        Simulates the 5-step pattern:
          1. AI calls explorer.analyze
          2. Gets file list back
          3. AI calls document_reader on a specific file
          4. Gets content back
          5. AI responds with final summary
        """
        explore_block = _make_tool_use_block(
            "tu_a", "explorer", {"operation": "find", "path": str(sample_dir), "pattern": "*.txt"}
        )
        read_block = _make_tool_use_block(
            "tu_b", "document_reader", {"path": str(sample_dir / "reports" / "q1_report.txt")}
        )

        resp1 = _make_response([explore_block], stop_reason="tool_use")
        resp2 = _make_response([read_block], stop_reason="tool_use")
        resp3 = _make_response([_make_text_block("Q1 profit was 400,000.")])

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [resp1, resp2, resp3]

        with patch("anthropic.Anthropic", return_value=mock_client):
            ai = AIClient(ANTHROPIC_CONFIG)

        tools = ToolRegistry(ANTHROPIC_CONFIG)
        perms = PermissionManager(ANTHROPIC_CONFIG)

        result = ai.reason_and_execute(
            f"Find all txt files in {sample_dir} and summarize the Q1 report",
            {"context": "financial analysis"},
            tools,
            perms,
        )

        assert result["iterations"] == 3
        assert len(result["tool_calls"]) == 2
        assert result["tool_calls"][0]["tool"] == "explorer"
        assert result["tool_calls"][1]["tool"] == "document_reader"
        assert "400,000" in result["response"]

    def test_parallel_tool_calls_in_one_step(self, tmp_path):
        """AI returns 2 tool_use blocks in a single response (parallel calls)."""
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("content a")
        f2.write_text("content b")

        block1 = _make_tool_use_block("tu_p1", "filesystem", {"operation": "read", "path": str(f1)})
        block2 = _make_tool_use_block("tu_p2", "filesystem", {"operation": "read", "path": str(f2)})

        resp1 = _make_response([block1, block2], stop_reason="tool_use")
        resp2 = _make_response([_make_text_block("Both files read.")])

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [resp1, resp2]

        with patch("anthropic.Anthropic", return_value=mock_client):
            ai = AIClient(ANTHROPIC_CONFIG)

        tools = ToolRegistry(ANTHROPIC_CONFIG)
        perms = PermissionManager(ANTHROPIC_CONFIG)

        result = ai.reason_and_execute("Read both files", {}, tools, perms)

        assert len(result["tool_calls"]) == 2
        contents = [tc["result"] for tc in result["tool_calls"]]
        assert "content a" in contents
        assert "content b" in contents


# ── Permission enforcement ────────────────────────────────────────────────────


class TestPermissions:
    def test_denied_path_returns_error_result(self, tmp_path):
        """When PermissionManager denies a tool call, we get an error result — not an exception."""
        tool_block = _make_tool_use_block(
            "tu_deny", "filesystem", {"operation": "read", "path": str(tmp_path / "secret.txt")}
        )
        first_response = _make_response([tool_block], stop_reason="tool_use")
        second_response = _make_response([_make_text_block("I couldn't read the file.")])

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [first_response, second_response]

        with patch("anthropic.Anthropic", return_value=mock_client):
            ai = AIClient(ANTHROPIC_CONFIG)

        tools = ToolRegistry(ANTHROPIC_CONFIG)

        # Restricted permission manager that denies everything
        strict_config = {
            "permissions": {
                "filesystem": {
                    "allowed_paths": ["/only/this/path"],
                    "denied_paths": [],
                    "max_file_size_mb": 50,
                },
                "shell": {"enabled": True, "allowed_commands": [], "denied_commands": []},
            }
        }
        perms = PermissionManager(strict_config)

        result = ai.reason_and_execute("Read secret file", {}, tools, perms)

        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["error"] is True
        assert "Permission denied" in result["tool_calls"][0]["result"]["error"]

    def test_unknown_tool_returns_error(self, tmp_path):
        """If AI calls a tool not in the registry, we get an error result."""
        tool_block = _make_tool_use_block("tu_unk", "ghost_tool", {"arg": "value"})
        first_response = _make_response([tool_block], stop_reason="tool_use")
        second_response = _make_response([_make_text_block("Tool not found.")])

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [first_response, second_response]

        with patch("anthropic.Anthropic", return_value=mock_client):
            ai = AIClient(ANTHROPIC_CONFIG)

        tools = ToolRegistry(ANTHROPIC_CONFIG)
        perms = PermissionManager(ANTHROPIC_CONFIG)

        result = ai.reason_and_execute("Use ghost tool", {}, tools, perms)

        assert result["tool_calls"][0]["error"] is True


# ── Max iterations safety ─────────────────────────────────────────────────────


class TestMaxIterations:
    def test_stops_at_max_iterations(self):
        """Loop never calls end_turn — must stop at max_iterations."""
        tool_block = _make_tool_use_block("tu_loop", "shell", {"command": "echo x"})
        looping_response = _make_response([tool_block], stop_reason="tool_use")

        mock_client = MagicMock()
        mock_client.messages.create.return_value = looping_response

        with patch("anthropic.Anthropic", return_value=mock_client):
            ai = AIClient(ANTHROPIC_CONFIG)

        tools = ToolRegistry(ANTHROPIC_CONFIG)
        perms = PermissionManager(ANTHROPIC_CONFIG)

        result = ai.reason_and_execute("loop forever", {}, tools, perms, max_iterations=3)

        assert result["iterations"] == 3
        assert mock_client.messages.create.call_count == 3


# ── Context injection ─────────────────────────────────────────────────────────


class TestContextInjection:
    def test_context_included_in_system_prompt(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_response([_make_text_block("Done.")])

        with patch("anthropic.Anthropic", return_value=mock_client):
            ai = AIClient(ANTHROPIC_CONFIG)

        tools = ToolRegistry(ANTHROPIC_CONFIG)
        perms = PermissionManager(ANTHROPIC_CONFIG)

        context = {"working_path": "/home/user/docs", "user": "alice"}
        ai.reason_and_execute("do task", context, tools, perms)

        call_kwargs = mock_client.messages.create.call_args[1]
        system_prompt = call_kwargs["system"]
        assert "working_path" in system_prompt
        assert "/home/user/docs" in system_prompt

    def test_tool_schemas_passed_to_api(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_response([_make_text_block("OK.")])

        with patch("anthropic.Anthropic", return_value=mock_client):
            ai = AIClient(ANTHROPIC_CONFIG)

        tools = ToolRegistry(ANTHROPIC_CONFIG)
        perms = PermissionManager(ANTHROPIC_CONFIG)

        ai.reason_and_execute("task", {}, tools, perms)

        call_kwargs = mock_client.messages.create.call_args[1]
        tool_names = [t["name"] for t in call_kwargs["tools"]]
        assert "filesystem" in tool_names
        assert "explorer" in tool_names
        assert "document_reader" in tool_names
        assert "shell" in tool_names


# ══════════════════════════════════════════════════════════════════════════════
# Akaion Backend agentic loop tests
# ══════════════════════════════════════════════════════════════════════════════

AKAION_CONFIG = {
    "ai": {
        "provider": "akaion",
        "model": "claude-opus-4-6",
        "temperature": 0.3,
        "max_tokens": 2000,
    },
    "tools": {"enabled": ["filesystem", "shell", "document_reader", "explorer"]},
    "permissions": {
        "filesystem": {"allowed_paths": [], "denied_paths": [], "max_file_size_mb": 50},
        "shell": {"enabled": True, "allowed_commands": [], "denied_commands": []},
    },
}


def _make_akaion_ai(mock_cloud_client):
    """
    Build AIClient with 'akaion' provider, injecting a mock cloud client.

    AuthManager is imported locally inside _init_akaion via `from .auth import AuthManager`,
    so we patch it at its source: runner.auth.AuthManager.
    AIBackendClient is imported at module level in ai_client, patched there.
    """
    with (
        patch("runner.auth.AuthManager") as MockAuth,
        patch("runner.ai_client.AIBackendClient", return_value=mock_cloud_client),
    ):
        mock_auth = MagicMock()
        mock_auth.get_api_key.return_value = "fake-key"
        mock_auth.get_runner_id.return_value = "runner-test-123"
        MockAuth.return_value = mock_auth
        return AIClient(AKAION_CONFIG)


def _akaion_turn(content_blocks, stop_reason="end_turn"):
    """Build a fake runner_agent_turn response dict."""
    return {
        "content": content_blocks,
        "stop_reason": stop_reason,
        "model": "claude-opus-4-6",
        "tokens_used": 100,
    }


def _text_block(text):
    return {"type": "text", "text": text}


def _tool_use_block(tu_id, name, input_data):
    return {"type": "tool_use", "id": tu_id, "name": name, "input": input_data}


class TestAkaionDirectResponse:
    def test_end_turn_on_first_call(self, tmp_path):
        mock_client = MagicMock()
        mock_client.runner_id = "runner-test-123"
        mock_client.runner_agent_turn.return_value = _akaion_turn(
            [_text_block("The answer is 42.")]
        )
        ai = _make_akaion_ai(mock_client)
        tools = ToolRegistry(AKAION_CONFIG)
        perms = PermissionManager(AKAION_CONFIG)

        result = ai.reason_and_execute("What is the answer?", {}, tools, perms)

        assert result["response"] == "The answer is 42."
        assert result["iterations"] == 1
        assert result["tool_calls"] == []
        mock_client.runner_agent_turn.assert_called_once()

    def test_backend_none_aborts_gracefully(self):
        mock_client = MagicMock()
        mock_client.runner_id = "runner-test-123"
        mock_client.runner_agent_turn.return_value = None  # backend unreachable

        ai = _make_akaion_ai(mock_client)
        tools = ToolRegistry(AKAION_CONFIG)
        perms = PermissionManager(AKAION_CONFIG)

        result = ai.reason_and_execute("do something", {}, tools, perms)
        # Should not raise, returns empty result
        assert "response" in result
        assert "tool_calls" in result


class TestAkaionSingleToolCall:
    def test_calls_filesystem_list(self, tmp_path):
        (tmp_path / "doc.txt").write_text("hello")

        mock_client = MagicMock()
        mock_client.runner_id = "runner-test-123"
        mock_client.runner_agent_turn.side_effect = [
            _akaion_turn(
                [
                    _tool_use_block(
                        "tu_1", "filesystem", {"operation": "list", "path": str(tmp_path)}
                    )
                ],
                stop_reason="tool_use",
            ),
            _akaion_turn([_text_block(f"Found doc.txt in {tmp_path}")]),
        ]

        ai = _make_akaion_ai(mock_client)
        tools = ToolRegistry(AKAION_CONFIG)
        perms = PermissionManager(AKAION_CONFIG)

        result = ai.reason_and_execute(f"List {tmp_path}", {}, tools, perms)

        assert result["iterations"] == 2
        assert len(result["tool_calls"]) == 1
        tc = result["tool_calls"][0]
        assert tc["tool"] == "filesystem"
        assert tc["error"] is False
        names = [i["name"] for i in tc["result"]]
        assert "doc.txt" in names

    def test_calls_explorer_map(self, sample_dir):
        mock_client = MagicMock()
        mock_client.runner_id = "runner-test-123"
        mock_client.runner_agent_turn.side_effect = [
            _akaion_turn(
                [
                    _tool_use_block(
                        "tu_2", "explorer", {"operation": "map", "path": str(sample_dir)}
                    )
                ],
                stop_reason="tool_use",
            ),
            _akaion_turn([_text_block("Tree mapped.")]),
        ]

        ai = _make_akaion_ai(mock_client)
        tools = ToolRegistry(AKAION_CONFIG)
        perms = PermissionManager(AKAION_CONFIG)

        result = ai.reason_and_execute(f"Map {sample_dir}", {}, tools, perms)
        tc = result["tool_calls"][0]
        assert tc["tool"] == "explorer"
        assert "reports" in tc["result"]["tree"]

    def test_calls_document_reader(self, tmp_path):
        f = tmp_path / "report.txt"
        f.write_text("Revenue: 5M\nProfit: 1.2M")

        mock_client = MagicMock()
        mock_client.runner_id = "runner-test-123"
        mock_client.runner_agent_turn.side_effect = [
            _akaion_turn(
                [_tool_use_block("tu_3", "document_reader", {"path": str(f)})],
                stop_reason="tool_use",
            ),
            _akaion_turn([_text_block("Revenue is 5M.")]),
        ]

        ai = _make_akaion_ai(mock_client)
        tools = ToolRegistry(AKAION_CONFIG)
        perms = PermissionManager(AKAION_CONFIG)

        result = ai.reason_and_execute(f"Read {f}", {}, tools, perms)
        assert "Revenue: 5M" in result["tool_calls"][0]["result"]["content"]

    def test_calls_shell_echo(self):
        mock_client = MagicMock()
        mock_client.runner_id = "runner-test-123"
        mock_client.runner_agent_turn.side_effect = [
            _akaion_turn(
                [_tool_use_block("tu_4", "shell", {"command": "echo akaion_runner"})],
                stop_reason="tool_use",
            ),
            _akaion_turn([_text_block("Shell output: akaion_runner")]),
        ]

        ai = _make_akaion_ai(mock_client)
        tools = ToolRegistry(AKAION_CONFIG)
        perms = PermissionManager(AKAION_CONFIG)

        result = ai.reason_and_execute("echo test", {}, tools, perms)
        assert result["tool_calls"][0]["result"]["stdout"].strip() == "akaion_runner"


class TestAkaionMultiStep:
    def test_explore_then_read_chain(self, sample_dir):
        mock_client = MagicMock()
        mock_client.runner_id = "runner-test-123"
        mock_client.runner_agent_turn.side_effect = [
            # Step 1: find .txt files
            _akaion_turn(
                [
                    _tool_use_block(
                        "tu_a",
                        "explorer",
                        {"operation": "find", "path": str(sample_dir), "pattern": "*.txt"},
                    )
                ],
                stop_reason="tool_use",
            ),
            # Step 2: read q1 report
            _akaion_turn(
                [
                    _tool_use_block(
                        "tu_b",
                        "document_reader",
                        {"path": str(sample_dir / "reports" / "q1_report.txt")},
                    )
                ],
                stop_reason="tool_use",
            ),
            # Step 3: final answer
            _akaion_turn([_text_block("Q1 profit was 400,000.")]),
        ]

        ai = _make_akaion_ai(mock_client)
        tools = ToolRegistry(AKAION_CONFIG)
        perms = PermissionManager(AKAION_CONFIG)

        result = ai.reason_and_execute(
            f"Find all txt files in {sample_dir} and summarize Q1", {}, tools, perms
        )

        assert result["iterations"] == 3
        assert len(result["tool_calls"]) == 2
        assert result["tool_calls"][0]["tool"] == "explorer"
        assert result["tool_calls"][1]["tool"] == "document_reader"
        assert "400,000" in result["response"]

    def test_messages_appended_correctly(self, tmp_path):
        """Verify that tool results are sent back in the messages array on the next call."""
        f = tmp_path / "x.txt"
        f.write_text("content x")

        mock_client = MagicMock()
        mock_client.runner_id = "runner-test-123"
        mock_client.runner_agent_turn.side_effect = [
            _akaion_turn(
                [_tool_use_block("tu_msg", "filesystem", {"operation": "read", "path": str(f)})],
                stop_reason="tool_use",
            ),
            _akaion_turn([_text_block("Done.")]),
        ]

        ai = _make_akaion_ai(mock_client)
        tools = ToolRegistry(AKAION_CONFIG)
        perms = PermissionManager(AKAION_CONFIG)
        ai.reason_and_execute(f"Read {f}", {}, tools, perms)

        # Second call should have 3 messages: initial user, assistant (tool_use), user (tool_result)
        second_call_kwargs = mock_client.runner_agent_turn.call_args_list[1][1]
        msgs = second_call_kwargs["messages"]
        assert len(msgs) == 3
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"
        assert msgs[2]["role"] == "user"
        # Last user message must contain tool_result
        result_blocks = msgs[2]["content"]
        assert any(b.get("type") == "tool_result" for b in result_blocks)

    def test_tool_schemas_sent_every_turn(self, tmp_path):
        mock_client = MagicMock()
        mock_client.runner_id = "runner-test-123"
        mock_client.runner_agent_turn.side_effect = [
            _akaion_turn(
                [_tool_use_block("tu_s", "shell", {"command": "echo hi"})],
                stop_reason="tool_use",
            ),
            _akaion_turn([_text_block("Done.")]),
        ]

        ai = _make_akaion_ai(mock_client)
        tools = ToolRegistry(AKAION_CONFIG)
        perms = PermissionManager(AKAION_CONFIG)
        ai.reason_and_execute("task", {}, tools, perms)

        # Both calls must pass tool schemas
        for call_args in mock_client.runner_agent_turn.call_args_list:
            tool_names = [t["name"] for t in call_args[1]["tools"]]
            assert "filesystem" in tool_names
            assert "shell" in tool_names
            assert "explorer" in tool_names
            assert "document_reader" in tool_names


class TestAkaionPermissionsAndErrors:
    def test_permission_denied_produces_error_result(self, tmp_path):
        mock_client = MagicMock()
        mock_client.runner_id = "runner-test-123"
        mock_client.runner_agent_turn.side_effect = [
            _akaion_turn(
                [
                    _tool_use_block(
                        "tu_d",
                        "filesystem",
                        {"operation": "read", "path": str(tmp_path / "secret.txt")},
                    )
                ],
                stop_reason="tool_use",
            ),
            _akaion_turn([_text_block("Permission denied.")]),
        ]

        ai = _make_akaion_ai(mock_client)
        tools = ToolRegistry(AKAION_CONFIG)

        strict_config = {
            "permissions": {
                "filesystem": {
                    "allowed_paths": ["/only/this/path"],
                    "denied_paths": [],
                    "max_file_size_mb": 50,
                },
                "shell": {"enabled": True, "allowed_commands": [], "denied_commands": []},
            }
        }
        perms = PermissionManager(strict_config)

        result = ai.reason_and_execute("read secret", {}, tools, perms)
        assert result["tool_calls"][0]["error"] is True
        assert "Permission denied" in result["tool_calls"][0]["result"]["error"]

    def test_unknown_tool_returns_error(self):
        mock_client = MagicMock()
        mock_client.runner_id = "runner-test-123"
        mock_client.runner_agent_turn.side_effect = [
            _akaion_turn(
                [_tool_use_block("tu_g", "ghost_tool", {"x": 1})],
                stop_reason="tool_use",
            ),
            _akaion_turn([_text_block("Tool not found.")]),
        ]

        ai = _make_akaion_ai(mock_client)
        tools = ToolRegistry(AKAION_CONFIG)
        perms = PermissionManager(AKAION_CONFIG)

        result = ai.reason_and_execute("use ghost", {}, tools, perms)
        assert result["tool_calls"][0]["error"] is True

    def test_max_iterations_guard(self):
        mock_client = MagicMock()
        mock_client.runner_id = "runner-test-123"
        mock_client.runner_agent_turn.return_value = _akaion_turn(
            [_tool_use_block("tu_loop", "shell", {"command": "echo x"})],
            stop_reason="tool_use",
        )

        ai = _make_akaion_ai(mock_client)
        tools = ToolRegistry(AKAION_CONFIG)
        perms = PermissionManager(AKAION_CONFIG)

        result = ai.reason_and_execute("loop", {}, tools, perms, max_iterations=3)
        assert result["iterations"] == 3
        assert mock_client.runner_agent_turn.call_count == 3


class TestAkaionContextAndSystem:
    def test_context_injected_in_system_prompt(self, tmp_path):
        mock_client = MagicMock()
        mock_client.runner_id = "runner-test-123"
        mock_client.runner_agent_turn.return_value = _akaion_turn([_text_block("ok")])

        ai = _make_akaion_ai(mock_client)
        tools = ToolRegistry(AKAION_CONFIG)
        perms = PermissionManager(AKAION_CONFIG)

        context = {"working_path": "/home/user/docs", "project": "akaion"}
        ai.reason_and_execute("task", context, tools, perms)

        call_kwargs = mock_client.runner_agent_turn.call_args[1]
        assert "working_path" in call_kwargs["system_prompt"]
        assert "/home/user/docs" in call_kwargs["system_prompt"]

    def test_runner_id_passed_correctly(self):
        mock_client = MagicMock()
        mock_client.runner_id = "my-runner-abc"
        mock_client.runner_agent_turn.return_value = _akaion_turn([_text_block("ok")])

        ai = _make_akaion_ai(mock_client)
        # Override the client runner_id
        ai.client.runner_id = "my-runner-abc"
        tools = ToolRegistry(AKAION_CONFIG)
        perms = PermissionManager(AKAION_CONFIG)

        ai.reason_and_execute("task", {}, tools, perms)

        call_kwargs = mock_client.runner_agent_turn.call_args[1]
        assert call_kwargs["runner_id"] == "my-runner-abc"
