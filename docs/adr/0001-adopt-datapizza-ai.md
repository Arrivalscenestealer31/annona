# 0001 — Adopt datapizza-ai as the agent vocabulary

- **Status:** Accepted
- **Date:** 2026-07-28
- **Deciders:** Akaion AI Lab
- **Supersedes:** —

## Context

The runner needed a provider-neutral way to represent a conversation: text,
tool calls, tool results, structured output, and the translation of each into
whatever a given provider expects on the wire.

Before Phase 0 there was no such representation. Each provider path built its own
message dictionaries inline, and the Akaion path stored provider response objects
in the transcript and replayed them on the next turn. A transcript was therefore
not a value: it could not be serialised, hashed, diffed or replayed — which
blocks the tamper-evident trace and the replay harness the research programme
depends on.

We could build that vocabulary ourselves, or adopt one.

## Decision

Adopt [`datapizza-ai`](https://github.com/datapizza-labs/datapizza-ai)
(`datapizza-ai-core`, MIT, Datapizza Labs) as the canonical message vocabulary
and the source of provider adapters.

Depend on the `-core` package only, and confine its types to L0 and L1 behind our
own value types and ports.

### What it supplies

| Component | Our use |
|---|---|
| `datapizza.type` — `TextBlock`, `FunctionCallBlock`, `FunctionCallResultBlock`, `StructuredBlock` | the canonical transcript vocabulary |
| `ROLE.anthropic_role`, `ROLE.google_role` | provider role translation we do not have to own |
| `datapizza.tools.Tool` | provider-neutral tool schemas; `Tool.schema` already matches our registry's `{name, description, parameters}` shape |
| `datapizza.clients.openai_like` | any OpenAI-compatible endpoint — Ollama, llama.cpp, vLLM — with `base_url` and `**kwargs` passthrough, so `guided_json` and `grammar` reach the runtime unmodified |
| `datapizza.agents.Agent` — `max_steps`, `Plan`, `before_step`/`after_step` | reference for the loop and planning; not used directly, see below |
| `datapizza-ai-eval` | harness substrate for the Lab Notes |

### What we keep

1. **The loop.** We use datapizza's types, not its `Agent`. See ADR
   [0002](0002-unify-the-agentic-loop.md).
2. **`ToolResultBlock`.** `FunctionCallResultBlock` carries a payload but no error
   flag. We subclass it rather than wrap it, so the value stays usable anywhere a
   datapizza block is expected while recording whether the call failed.
3. **Schema-only tools.** `as_datapizza_tool` builds a `Tool` with no callable
   attached. The runner executes tools itself, under policy; a framework-held
   reference to a live function would be a way around that.

## Alternatives considered

**Define our own message types.** Two to three days, total control. Rejected: the
work is not the types, it is the per-provider translation behind them, and that
is exactly what datapizza already maintains. We would have spent the Phase 0
budget rebuilding the least differentiated part of the system.

**Use `datapizza.agents.Agent` as the loop as well.** Rejected in
[0002](0002-unify-the-agentic-loop.md) — its extension point is a step hook, and
a step hook is the wrong place for a security boundary.

**LangChain / LlamaIndex.** Rejected: dependency surface far larger than the
problem, and both want to own the control flow, which is the one thing we cannot
delegate.

## Consequences

**Good.**

- The transcript is a value. It serialises, so it can be hashed, replayed and
  audited — the precondition for Phase 3.
- Local runtimes are reachable through `openai_like` today, without a fork, and
  constrained decoding parameters pass straight through.
- Building on an Italian open framework is coherent with what the lab claims to
  be: an ecosystem participant, not a proprietor. The grammar-constrained clients
  we write in Phase 2 are candidates to upstream.

**Bad, and accepted.**

- A young dependency: public since October 2025, ~2.2k stars, ~212 commits at
  adoption. Mitigations: `-core` only (its most stable surface), exact version
  pin, our own value types at the boundary. Replacing it would touch L0 and L1,
  not the loop.
- Their `Tool` and blocks are mutable classes rather than frozen values, so our
  own types stay the ones that cross layer boundaries.

**Neutral.** MIT is compatible with this project's Apache-2.0 licence; the
attribution is recorded in `NOTICE`.

## Verification

- `tests/test_kernel.py` covers the translation in both directions.
- `.importlinter` forbids provider SDKs from L0 and L3, so the dependency cannot
  spread beyond where this decision puts it.
