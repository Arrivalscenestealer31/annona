# ── When the model writes the tool call instead of emitting it ───────────────


def _decoded(content: str):
    from runner.capability.backends.ollama import _decode

    return _decode({"message": {"content": content}})


def test_a_tool_call_written_as_text_is_recovered():
    """Observed on qwen2.5:14b, on a prompt that had worked a minute earlier.

    The intent is right and the arguments are right; only the channel is wrong.
    Without this the run produces prose containing JSON and no tool ever runs.
    """
    completion = _decoded(
        ' forCell\n{"name": "document_reader", "arguments": {"path": "/tmp/x.txt"}}\n</tool_call>'
    )

    assert completion.wants_tools
    assert completion.tool_calls[0].name == "document_reader"
    assert completion.tool_calls[0].arguments == {"path": "/tmp/x.txt"}


def test_the_recovered_call_is_removed_from_the_answer():
    """Otherwise the user sees the machinery in their answer."""
    completion = _decoded('Ecco:\n<tool_call>{"name": "explorer", "arguments": {}}</tool_call>')

    assert "tool_call" not in completion.text
    assert completion.text.strip() == "Ecco:"


def test_prose_that_merely_contains_braces_is_not_a_tool_call():
    completion = _decoded("Il file contiene {qualcosa} fra parentesi graffe.")

    assert not completion.wants_tools
    assert completion.text.startswith("Il file")


def test_malformed_json_in_the_text_is_left_alone():
    completion = _decoded('{"name": "explorer", "arguments": {')

    assert not completion.wants_tools


def test_a_native_tool_call_is_never_second_guessed():
    from runner.capability.backends.ollama import _decode

    completion = _decode(
        {
            "message": {
                "content": '{"name": "ignored", "arguments": {}}',
                "tool_calls": [{"function": {"name": "real", "arguments": {"a": 1}}}],
            }
        }
    )

    assert [c.name for c in completion.tool_calls] == ["real"]
