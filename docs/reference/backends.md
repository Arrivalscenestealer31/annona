# Inference backends

A backend performs **one turn of inference** and nothing else. It holds no
conversation state, makes no decision about whether to continue, and — from Phase
1 — no decision about whether it may be called at all.

## The port

```python
class InferenceBackend(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def capabilities(self) -> Capabilities: ...

    def complete(self, request: CompletionRequest) -> Completion: ...
```

Structural: implement the shape and you are a backend. No base class, no
registration.

## Shipped

| Backend | `is_local` | Native tools | Grammar | Module |
|---|---|---|---|---|
| `echo` | **yes** | yes | none | `capability/backends/echo.py` |
| `anthropic` | no | yes | none | `capability/backends/anthropic.py` |
| `akaion` | no | yes | none | `capability/backends/akaion.py` |

Planned for Phase 2: `ollama`, `llamacpp`, `vllm` — the first backends where
`is_local` is `True` *and* a real model is doing the work.

## `Capabilities`

```python
@dataclass(frozen=True, slots=True)
class Capabilities:
    native_tools: bool = False
    grammar: GrammarSupport = "none"    # none | json_schema | gbnf | guided
    parallel_tool_calls: bool = False
    context_window: int = 0
    is_local: bool = False
```

Defaults are conservative: a backend that declares nothing is treated as remote
and incapable. Under-claiming costs a little performance; over-claiming costs
correctness, and in the case of `is_local`, it costs the whole product promise.

### `is_local` is the important field

It answers one question: **does calling this backend constitute egress?**

Declared once, by the adapter that knows, instead of inferred at each call site.
That is what makes the single-chokepoint property of Phase 1 statable at all —
the perimeter reads this field and gates the call. Today nothing reads it, which
is the gap the README documents.

For `akaion` and `anthropic` it is `False`, and the reason is worth stating
plainly: the transcript accumulates tool results, so **everything the agent reads
is sent** on the following turn.

### `grammar`

Unused in Phase 0, declared now so backends can be honest from the start.

| Value | Meaning |
|---|---|
| `none` | Free text. Tool calls parsed hopefully (tier 3) |
| `json_schema` | Output can be shaped, not provably constrained (Ollama `format`) |
| `gbnf` | llama.cpp grammars — a malformed tool call becomes structurally impossible |
| `guided` | vLLM guided decoding, same property |

Tier 2 (`gbnf` / `guided`) is the Phase 2 unlock: constrain generation with a
grammar compiled from the tool's JSON Schema and schema violations go to zero by
construction. See [Research](../research/index.md).

## Writing one

Three rules, in order of importance:

1. **Declare `is_local` truthfully.** Everything else is a performance detail;
   this one is a safety property.
2. **Do not catch provider errors.** A 401 or a rate limit must propagate. Raise
   `BackendUnavailableError` only when the provider returned *nothing usable* —
   that is the one condition the loop treats as "stop and report what you have".
3. **Own your wire format and nothing else.** No state, no control flow.

```python
from runner.capability.backends.wire import decode_completion, encode_tools, encode_transcript
from runner.kernel.types import Capabilities, Completion, CompletionRequest


class MyBackend:
    def __init__(self, client, model: str) -> None:
        self._client = client
        self._model = model

    @property
    def name(self) -> str:
        return "mine"

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(native_tools=True, is_local=True, context_window=32_000)

    def complete(self, request: CompletionRequest) -> Completion:
        response = self._client.chat(
            model=request.model or self._model,
            system=request.system,
            messages=encode_transcript(request.transcript),
            tools=encode_tools(request.tools),
        )
        return decode_completion(response["content"], response.get("stop_reason"))
```

Then wire it in `AIClient.build_backend` — the composition root is where clients
get constructed, because that is where credentials and the environment live. An
adapter that builds its own client is an adapter you cannot substitute in a test.

`wire.py` is Anthropic-shaped and shared by the two remote backends. A provider
with a different vocabulary writes its own encoder; the `Completion` it returns is
what makes it interchangeable, not how it got there.

## Testing one

Test through the loop, not through a mock of your provider:

```python
from runner.agent.loop import AgentLoop

result = AgentLoop(MyBackend(fake_client, "m"), executor, gate).run("task")
```

`tests/test_backends.py` covers the shipped three and the shared encoder. The
encoder tests are the ones that matter most: two adapters share it, and drift
between those two paths is the failure this architecture exists to prevent.
