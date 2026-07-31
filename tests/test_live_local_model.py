"""Live tests against a real local model. Opt-in, and worth running.

Everything else in this suite proves the perimeter behaves correctly against
scripted substrates. These prove it behaves correctly against a model that has
opinions: one that decides on its own whether to call a tool, gets the arguments
wrong sometimes, and answers in whatever prose it likes.

Enabled with::

    ANNONA_LIVE_OLLAMA=1 pytest -m live
    ANNONA_LIVE_MODEL=qwen2.5:14b ANNONA_LIVE_OLLAMA=1 pytest -m live

Skipped otherwise, so CI without a GPU is not red for a reason nobody can fix.
The same tests are what runs on a DGX before it is handed to a customer — the
model changes, the assertions do not.
"""

from __future__ import annotations

import os

import pytest

from runner.agent.loop import AgentLoop
from runner.audit.ledger import verify_file
from runner.capability.backends.ollama import OllamaBackend
from runner.capability.backends.openai_compatible import OpenAICompatibleBackend
from runner.kernel.blocks import text_block
from runner.kernel.types import (
    Capabilities,
    Completion,
    CompletionRequest,
    SensitivityClass,
    ToolCall,
    ToolResult,
    ToolSpec,
    Turn,
)
from runner.policy.loader import parse_policy
from runner.services.enforcement import Enforcement

pytestmark = [pytest.mark.live, pytest.mark.slow]

ENDPOINT = os.getenv("ANNONA_LIVE_ENDPOINT", "http://localhost:11434")
MODEL = os.getenv("ANNONA_LIVE_MODEL", "qwen2.5:3b")
CANARY = "ANNONA-CANARY-7f3a91"

pytestmark.append(
    pytest.mark.skipif(
        os.getenv("ANNONA_LIVE_OLLAMA") != "1",
        reason="set ANNONA_LIVE_OLLAMA=1 (and have a model pulled) to run live tests",
    )
)


READER = ToolSpec(
    name="document_reader",
    description="Read a document from disk and return its text.",
    schema={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Absolute path to the file"}},
        "required": ["path"],
    },
)


class Wiretap:
    """A substrate that records everything sent to it and answers blandly.

    Stands in for a frontier API in the leak tests: if a byte of client material
    reaches it, the test fails with the payload attached.
    """

    def __init__(self, name="frontier"):
        self._name = name
        self.received: list[str] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(native_tools=True, is_local=False, context_window=200_000)

    def complete(self, request: CompletionRequest) -> Completion:
        self.received.append(
            request.system
            + "\n"
            + "\n".join(str(getattr(b, "content", b)) for t in request.transcript for b in t.blocks)
        )
        return Completion(text_parts=("acknowledged",), stop_reason="end_turn")


class RealFiles:
    """A tool that really reads the filesystem."""

    def __init__(self):
        self.reads: list[str] = []

    def specs(self):
        return (READER,)

    def invoke(self, call: ToolCall) -> ToolResult:
        path = str(call.arguments.get("path", ""))
        self.reads.append(path)
        try:
            with open(path) as handle:
                return ToolResult(call_id=call.id, name=call.name, content=handle.read())
        except OSError as exc:
            return ToolResult(call_id=call.id, name=call.name, content=str(exc), is_error=True)


# ── The backend itself ────────────────────────────────────────────────────────


def test_the_local_model_answers():
    backend = OllamaBackend(model=MODEL, endpoint=ENDPOINT)
    completion = backend.complete(
        CompletionRequest(
            system="Answer in exactly one word.",
            transcript=(Turn(role="user", blocks=(text_block("What is the capital of Italy?"),)),),
            temperature=0.0,
        )
    )
    assert "rom" in completion.text.lower()


def test_the_local_model_is_declared_local():
    """The field the perimeter reads before deciding this is not egress."""
    assert OllamaBackend(model=MODEL, endpoint=ENDPOINT).capabilities.is_local is True


def test_the_local_model_calls_a_tool_with_usable_arguments(tmp_path):
    """Tier 1: native tool calling on a model that was trained for it.

    The measured claim from the research programme is that small models get the
    *intent* right and the *arguments* wrong. This asserts the intent, and
    reports the argument quality rather than pretending it is perfect.
    """
    document = tmp_path / "report.txt"
    document.write_text("Q1 2026: 142 matters opened, 98 closed.")

    backend = OllamaBackend(model=MODEL, endpoint=ENDPOINT)
    completion = backend.complete(
        CompletionRequest(
            system=(
                "You are a file-reading assistant. To read a file you MUST call the "
                "document_reader tool with the absolute path. Never guess contents."
            ),
            transcript=(
                Turn(
                    role="user",
                    blocks=(text_block(f"Read the file at {document} and tell me what it says."),),
                ),
            ),
            tools=(READER,),
            temperature=0.0,
        )
    )

    assert completion.wants_tools, "the model did not call the tool at all"
    call = completion.tool_calls[0]
    assert call.name == "document_reader"
    assert call.arguments.get("path"), (
        "the model called the right tool with no path — the malformed-arguments "
        "failure that grammar-constrained decoding is meant to close"
    )


def test_the_openai_compatible_path_reaches_the_same_server():
    """Ollama also speaks /v1, which is what a vLLM appliance speaks natively.

    Exercising both adapters against one server means the DGX path is covered on
    a laptop, rather than only on hardware nobody has during development.
    """
    backend = OpenAICompatibleBackend(
        model=MODEL,
        endpoint=f"{ENDPOINT}/v1",
        context_window=32_000,
    )
    completion = backend.complete(
        CompletionRequest(
            system="Answer in exactly one word.",
            transcript=(Turn(role="user", blocks=(text_block("What is 2 + 2?"),)),),
            temperature=0.0,
        )
    )
    assert completion.text.strip()


# ── The perimeter, with a real model behind it ────────────────────────────────


def live_policy(tmp_path):
    return parse_policy(
        {
            "version": 1,
            "default": "deny",
            "classes": {
                "restricted": {
                    "paths": [f"{tmp_path}/clients/**"],
                    "patterns": [r"[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]"],
                },
                "internal": {"paths": [f"{tmp_path}/**"]},
                "public": {"default": True},
            },
            "substrates": [
                {
                    "id": "local-gpu",
                    "kind": "ollama",
                    "endpoint": ENDPOINT,
                    "model": MODEL,
                    "jurisdiction": "on-prem",
                    "max_class": "restricted",
                    "context_window": 32000,
                },
                {
                    "id": "frontier",
                    "kind": "echo",
                    "jurisdiction": "us",
                    "max_class": "public",
                    "quality": 99,
                },
            ],
            "rules": [
                {"id": "R-restricted", "match": {"class": "restricted"}, "allow": ["local-gpu"]},
                {"id": "R-internal", "match": {"class": "internal"}, "allow": ["local-gpu"]},
                {
                    "id": "R-public",
                    "match": {"class": "public"},
                    "allow": ["frontier", "local-gpu"],
                    "prefer": "quality",
                },
            ],
            "egress": {"canaries": [CANARY]},
            "tools": {"allow": {"document_reader": [f"{tmp_path}/**"]}, "deny_paths": []},
        }
    )


def test_a_real_model_reading_a_real_client_file_never_leaks_it(tmp_path):
    """The acceptance test, with nothing scripted except the wiretap.

    A local model decides for itself to read a client file. From that moment the
    run is restricted, and every later turn has to stay on the machine. The
    frontier substrate is present, healthy, higher quality, and never sees a
    thing.
    """
    client_dir = tmp_path / "clients"
    client_dir.mkdir()
    matter = client_dir / "BG-114.txt"
    matter.write_text(f"Cliente RSSMRA85T10A562S, pratica 2026/114, scadenza 15 marzo. {CANARY}")

    frontier = Wiretap()
    enforcement = Enforcement.for_run(
        policy=live_policy(tmp_path),
        ledger_path=tmp_path / "ledger.jsonl",
        backends={
            "local-gpu": OllamaBackend(model=MODEL, endpoint=ENDPOINT),
            "frontier": frontier,
        },
        probe=True,
        fsync=False,
        run_id="live",
    )

    tools = RealFiles()
    loop = AgentLoop(enforcement.backend(), enforcement.executor(tools), enforcement.gate())
    result = loop.run(
        f"Read the file at {matter} using the document_reader tool, then tell me the deadline.",
        max_iterations=4,
    )

    assert tools.reads, "the model never read the file, so the test proved nothing"
    assert enforcement.klass is SensitivityClass.RESTRICTED

    leaked = [seen for seen in frontier.received if CANARY in seen or "RSSMRA85T10A562S" in seen]
    assert leaked == [], f"leak rate is not zero: {leaked}"

    assert verify_file(enforcement.ledger.path).ok
    placements = [e for e in enforcement.ledger.entries() if e.kind == "inference"]
    assert any(e.substrate == "local-gpu" for e in placements)
    assert result.iterations >= 2


def test_with_the_local_model_unreachable_restricted_work_is_held(tmp_path):
    """Same policy, dead GPU: the frontier is up and stays unused."""
    matter = tmp_path / "clients" / "x.txt"
    matter.parent.mkdir()
    matter.write_text("Cliente RSSMRA85T10A562S")

    frontier = Wiretap()
    enforcement = Enforcement.for_run(
        policy=live_policy(tmp_path),
        ledger_path=tmp_path / "ledger.jsonl",
        backends={
            # A port nothing listens on: the failure a real outage produces.
            "local-gpu": OllamaBackend(model=MODEL, endpoint="http://127.0.0.1:1", timeout=2.0),
            "frontier": frontier,
        },
        probe=False,
        fsync=False,
    )
    enforcement.working_set.observe(str(matter), SensitivityClass.RESTRICTED)

    loop = AgentLoop(enforcement.backend(), enforcement.executor(RealFiles()), enforcement.gate())
    result = loop.run("summarise the client file", max_iterations=2)

    assert result.response == ""
    assert frontier.received == []
    held = [e for e in enforcement.ledger.entries() if e.outcome == "held"]
    assert held
