"""End-to-end: a full agentic run with no mocks below the backend.

Everything under the inference call is real here — the tool registry, the tools
themselves reading real files, the permission manager, the transcript. Only the
reasoning is scripted, because a deterministic test cannot depend on a model.

This is the test that would catch a wiring regression the unit tests cannot see:
each layer can be individually correct and still not compose.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from runner.demo import _denied_script, _script, _workspace, main, run_demo

pytestmark = [pytest.mark.e2e, pytest.mark.integration]


@pytest.fixture
def documents(tmp_path: Path) -> Path:
    return _workspace(tmp_path)


class TestPermittedRun:
    def test_explores_reads_and_answers(self, documents: Path):
        result = run_demo(documents, _script(documents))

        assert result.iterations == 3
        assert [c.tool for c in result.tool_calls] == ["explorer", "document_reader"]
        assert not any(c.error for c in result.tool_calls)
        assert "412.000" in result.response

    def test_the_tools_really_touched_the_filesystem(self, documents: Path):
        """Not a stub: the explorer saw the tree and the reader read the bytes."""
        result = run_demo(documents, _script(documents))

        assert "reports" in str(result.tool_calls[0].result)
        assert "Fatturato" in str(result.tool_calls[1].result)

    def test_the_second_tool_call_used_a_real_path(self, documents: Path):
        result = run_demo(documents, _script(documents))

        read_path = Path(result.tool_calls[1].input["path"])
        assert read_path.exists()
        assert read_path.is_relative_to(documents)


class TestPolicyEnforcement:
    def test_a_path_outside_the_allow_list_is_refused(self, documents: Path):
        result = run_demo(documents, _denied_script(documents))

        denial = result.tool_calls[0]
        assert denial.error is True
        assert denial.result == {"error": "Permission denied for tool: filesystem"}

    def test_the_run_continues_after_a_denial(self, documents: Path):
        """A refusal is an answer to the model, not the end of the task."""
        result = run_demo(documents, _denied_script(documents))

        assert result.iterations == 2
        assert result.response == "I was not allowed to read that."


class TestCliEntryPoint:
    def test_check_mode_succeeds(self, capsys):
        """The exact invocation CI runs on every push."""
        assert main(["--check"]) == 0
        assert "ok" in capsys.readouterr().out

    def test_narrated_mode_succeeds(self, capsys):
        assert main([]) == 0

        out = capsys.readouterr().out
        assert "offline demo" in out
        assert "denied" in out
