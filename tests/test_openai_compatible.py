"""The OpenAI-compatible wire format, which is what a DGX actually speaks.

vLLM is what serves the appliance, and this adapter is the only thing between a
policy decision and that server. The tests are about the two places this dialect
bites: tool call arguments arrive as a JSON *string*, and every assistant tool
call must be answered by a ``role: "tool"`` message carrying the same id or the
server rejects the whole conversation.

No network: an injected client records what would have been sent.
"""

from __future__ import annotations

import json

import httpx
import pytest

from runner.capability.backends.openai_compatible import OpenAICompatibleBackend
from runner.kernel.blocks import function_call_block, function_result_block, text_block
from runner.kernel.errors import BackendUnavailableError
from runner.kernel.types import (
    CompletionRequest,
    ToolCall,
    ToolResult,
    ToolSpec,
    Turn,
)

pytestmark = pytest.mark.unit


class FakeClient:
    """Captures the request and returns a canned response."""

    def __init__(self, payload=None, status: int = 200, raises: Exception | None = None):
        self.payload = payload or {"choices": [{"message": {"content": "hello"}}]}
        self.status = status
        self.raises = raises
        self.sent: dict = {}
        self.headers: dict = {}
        self.url = ""

    def post(self, url, json=None, headers=None):
        if self.raises:
            raise self.raises
        self.url = url
        self.sent = json or {}
        self.headers = headers or {}
        return httpx.Response(self.status, json=self.payload, request=httpx.Request("POST", url))


def backend(client, **kwargs):
    return OpenAICompatibleBackend("qwen", "http://gpu:8000/v1", client=client, **kwargs)


TOOL = ToolSpec(
    name="document_reader",
    description="Read a document",
    schema={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
)


# ── Encoding ──────────────────────────────────────────────────────────────────


def test_it_posts_to_chat_completions_on_the_declared_endpoint():
    client = FakeClient()
    backend(client).complete(CompletionRequest(system="be brief", transcript=()))
    assert client.url == "http://gpu:8000/v1/chat/completions"


def test_the_system_prompt_becomes_the_first_message():
    client = FakeClient()
    backend(client).complete(CompletionRequest(system="be brief", transcript=()))
    assert client.sent["messages"][0] == {"role": "system", "content": "be brief"}


def test_tools_are_sent_in_the_function_shape():
    client = FakeClient()
    backend(client).complete(CompletionRequest(system="", transcript=(), tools=(TOOL,)))

    tool = client.sent["tools"][0]
    assert tool["type"] == "function"
    assert tool["function"]["name"] == "document_reader"
    assert tool["function"]["parameters"]["required"] == ["path"]
    assert client.sent["tool_choice"] == "auto"


def test_no_tools_means_no_tool_fields():
    """Sending an empty tools array makes some servers refuse the request."""
    client = FakeClient()
    backend(client).complete(CompletionRequest(system="", transcript=()))
    assert "tools" not in client.sent
    assert "tool_choice" not in client.sent


def test_a_tool_round_trip_keeps_call_ids_paired():
    """The pairing servers reject conversations over."""
    client = FakeClient()
    call = ToolCall(id="call_abc", name="document_reader", arguments={"path": "/tmp/x"})
    result = ToolResult(call_id="call_abc", name="document_reader", content="the contents")

    backend(client).complete(
        CompletionRequest(
            system="",
            transcript=(
                Turn(role="user", blocks=(text_block("read it"),)),
                Turn(role="assistant", blocks=(function_call_block(call, TOOL),)),
                Turn(role="user", blocks=(function_result_block(result, TOOL),)),
            ),
            tools=(TOOL,),
        )
    )

    messages = client.sent["messages"]
    assistant = next(m for m in messages if m.get("tool_calls"))
    tool_message = next(m for m in messages if m["role"] == "tool")

    assert assistant["role"] == "assistant"
    assert assistant["tool_calls"][0]["id"] == tool_message["tool_call_id"]
    assert json.loads(assistant["tool_calls"][0]["function"]["arguments"]) == {"path": "/tmp/x"}
    assert tool_message["content"] == "the contents"


def test_a_failed_tool_result_says_so_in_the_text():
    """There is no error flag in this dialect, so it has to be legible."""
    client = FakeClient()
    result = ToolResult(call_id="c", name="document_reader", content="denied", is_error=True)

    backend(client).complete(
        CompletionRequest(
            system="",
            transcript=(Turn(role="user", blocks=(function_result_block(result, TOOL),)),),
        )
    )

    tool_message = next(m for m in client.sent["messages"] if m["role"] == "tool")
    assert tool_message["content"].startswith("ERROR:")


def test_an_api_key_is_only_sent_when_there_is_one():
    without = FakeClient()
    backend(without).complete(CompletionRequest(system="", transcript=()))
    assert without.headers == {}

    with_key = FakeClient()
    backend(with_key, api_key="sk-test").complete(CompletionRequest(system="", transcript=()))
    assert with_key.headers["Authorization"] == "Bearer sk-test"


# ── Decoding ──────────────────────────────────────────────────────────────────


def test_plain_text_becomes_a_completion():
    completion = backend(FakeClient()).complete(CompletionRequest(system="", transcript=()))
    assert completion.text == "hello"
    assert completion.stop_reason == "end_turn"
    assert not completion.wants_tools


def test_tool_calls_are_decoded_from_their_json_string():
    client = FakeClient(
        {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "function": {
                                    "name": "document_reader",
                                    "arguments": '{"path": "/mnt/report.pdf"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }
    )
    completion = backend(client).complete(CompletionRequest(system="", transcript=()))

    assert completion.wants_tools
    assert completion.tool_calls[0].name == "document_reader"
    assert completion.tool_calls[0].arguments == {"path": "/mnt/report.pdf"}


def test_malformed_tool_arguments_do_not_end_the_run():
    """The characteristic failure of a small model, and the case for grammars.

    An unparseable argument object becomes an empty one, which the loop turns
    into a tool error the model can read and retry from. Crashing here would
    make every 3B model unusable.
    """
    client = FakeClient(
        {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {"id": "c", "function": {"name": "document_reader", "arguments": "{path: "}}
                        ]
                    }
                }
            ]
        }
    )
    completion = backend(client).complete(CompletionRequest(system="", transcript=()))

    assert completion.tool_calls[0].name == "document_reader"
    assert completion.tool_calls[0].arguments == {}


def test_arguments_already_decoded_are_accepted():
    """Some servers send an object where the spec says string. Both work."""
    client = FakeClient(
        {
            "choices": [
                {"message": {"tool_calls": [{"id": "c", "function": {"name": "t", "arguments": {"a": 1}}}]}}
            ]
        }
    )
    completion = backend(client).complete(CompletionRequest(system="", transcript=()))
    assert completion.tool_calls[0].arguments == {"a": 1}


# ── Failure modes ─────────────────────────────────────────────────────────────


def test_an_unreachable_server_is_unavailable_not_a_crash():
    client = FakeClient(raises=httpx.ConnectError("connection refused"))
    with pytest.raises(BackendUnavailableError, match="unreachable"):
        backend(client).complete(CompletionRequest(system="", transcript=()))


def test_a_missing_model_says_which_model():
    client = FakeClient({"error": "not found"}, status=404)
    with pytest.raises(BackendUnavailableError, match="qwen"):
        backend(client).complete(CompletionRequest(system="", transcript=()))


def test_a_server_error_is_unavailable():
    client = FakeClient({"error": "overloaded"}, status=503)
    with pytest.raises(BackendUnavailableError, match="503"):
        backend(client).complete(CompletionRequest(system="", transcript=()))


def test_an_unreadable_response_is_unavailable_rather_than_an_exception():
    client = FakeClient({"unexpected": "shape"})
    with pytest.raises(BackendUnavailableError, match="cannot read"):
        backend(client).complete(CompletionRequest(system="", transcript=()))


# ── Capabilities ──────────────────────────────────────────────────────────────


def test_locality_is_declared_by_the_operator_not_guessed():
    """An HTTP client cannot know whose datacentre it is talking to."""
    assert backend(FakeClient(), is_local=True).capabilities.is_local is True
    assert backend(FakeClient(), is_local=False).capabilities.is_local is False


def test_grammar_support_is_not_overclaimed():
    """vLLM can constrain generation; this adapter does not ask it to yet."""
    assert backend(FakeClient()).capabilities.grammar == "json_schema"
