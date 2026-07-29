# 0002 — Unify the agentic loop behind ports

- **Status:** Accepted
- **Date:** 2026-07-28
- **Deciders:** Akaion AI Lab
- **Supersedes:** —

## Context

`runner/ai_client.py` implemented the agentic loop three times:

| Provider | Method | Tool use | Loop owner |
|---|---|---|---|
| `akaion` | `_agentic_loop_akaion` | yes | runner holds state, control plane performs each turn |
| `anthropic` | `_agentic_loop_anthropic` | yes | runner |
| `openai`, `google`, `local` | `_agentic_loop_generic` | **no** | nobody — degraded to chat completion |

Three consequences, in ascending order of seriousness:

1. **Local mode could not act.** With `ai.provider: local` the agent could hold a
   conversation and not touch a file. The appliance story had no execution path.
2. **Divergence.** The two real loops had already drifted: one joined every text
   block in a turn, the other kept only the last.
3. **Three egress sites.** Content could leave the perimeter from three
   independent places. Privacy-constrained routing, a hash-chained trace and a
   measured leak rate all require exactly one, so none of them was implementable.

The third is the reason this is an ADR and not a cleanup ticket.

## Decision

One loop, in `runner/agent/loop.py`, depending only on ports declared in
`runner/kernel/ports.py`:

- `InferenceBackend` — one turn of inference
- `ToolExecutor` — advertises and runs tools
- `PolicyGate` — decides whether a call may run

Providers become L1 adapters. `AIClient` becomes the composition root: it
constructs provider clients — where credentials and the environment live — and
wires ports to adapters.

**Ports live in L0, not in L1.** This is the load-bearing detail. If the loop
imported the backend package, "the loop knows nothing about providers" would be a
convention. With ports in the innermost layer, it is a checked fact:

```ini
[importlinter:contract:agent-has-no-vendors]
type = forbidden
source_modules = runner.agent
forbidden_modules = anthropic, openai, google, httpx
```

Phase 1 then inserts the perimeter by passing a *different* `InferenceBackend` —
one that classifies and gates before delegating — and a different `PolicyGate`.
Neither the loop nor the adapters change.

## Behaviour: preserved, with three exceptions

The existing suite (205 tests, including 34 covering both loops through mocked
SDKs) passes unchanged. Three differences are deliberate and none is reachable by
those tests.

**1. Text aggregation is now uniform.** The Akaion path kept only the last text
block of a turn; the Anthropic path joined them all. Joining is now used for
both. A model that comments before calling a tool had its commentary silently
discarded on the Akaion path.

**2. A zero iteration budget returns instead of raising.** `max_iterations=0`
previously raised `UnboundLocalError` from an unbound loop variable. It now
returns an empty result.

**3. Unserialisable tool results degrade instead of raising.** Encoding a tool
result used `json.dumps` with no fallback, so a `Path` in a result raised
mid-run. It now falls back to `default=str`.

Also preserved deliberately: **provider exceptions are not caught.** A 401 or a
rate limit propagates exactly as before. Swallowing it would turn a credentials
failure into a silently empty answer. Only `BackendUnavailableError` — which an
adapter raises when the provider returns nothing usable — stops the loop
gracefully, which is what the Akaion path already did.

## Alternatives considered

**Add a fourth `_agentic_loop_local`.** Two days, ships local tool use
immediately. Rejected: four egress sites instead of three, so every control in
the research programme would have to be built and audited four times, and the
egress-totality property becomes unstateable. It buys a demo and mortgages the
programme.

**Use `datapizza.agents.Agent` as the loop.** It has `max_steps`, a typed `Plan`
and `before_step`/`after_step` hooks. Rejected on one point: the extension point
is a *step* hook, and the perimeter must gate the *inference call*. A step hook
observes a decision already made; a control-flow bug can route around it, and no
bug can route around a wrapped client. Observability belongs in step hooks;
security does not.

**Move the tools and the permission manager into the new layers now.** Rejected
as scope: Phase 0 must keep the suite green, and relocating those packages
changes import paths across the codebase. They stay where they are behind
adapters (`runner/capability/tooling.py`) and move during the layout migration.

## Consequences

**Good.**

- One place where content can leave the perimeter. Phase 1 has somewhere to stand.
- The loop is testable without mocking a vendor SDK
  (`tests/test_agent_loop_unified.py`).
- A new provider is an adapter, not a loop.
- ~244 lines of duplicated control flow deleted.

**Bad, and accepted.**

- The layout is now inconsistent: `runner/kernel`, `runner/capability` and
  `runner/agent` sit beside `runner/tools`, `runner/brain` and `runner/sync`,
  which have not moved. The tree does not yet look like the design document. The
  alternative was a big-bang move during a refactor that must not break anything.
- `openai`, `google` and `local` still route to the tool-less fallback. Phase 0
  did not close that gap; it made closing it a matter of writing one adapter.

## Verification

- `tests/test_agentic_loop.py` — unchanged, proves the observable behaviour of
  both real paths is intact.
- `tests/test_agent_loop_unified.py` — the loop through its ports.
- `tests/test_backends.py` — the adapters and the shared wire format.
- `tests/test_demo_e2e.py` — the layers composed, end to end, offline.
- `lint-imports` — five contracts, enforced in CI.
