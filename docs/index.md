---
hide:
  - navigation
---

<div class="dg-hero" markdown="1">
<span class="dg-hero__eyebrow">Akaion AI Lab · Apache-2.0</span>

<h1 class="dg-hero__title">Ann<span class="dg-hero__stamp">ona</span></h1>

<p class="dg-hero__tagline">Where it runs is a decision.</p>

<p class="dg-hero__sub">
The sovereign execution kernel for AI agents. Annona takes a plan and, for every
step, decides where it may run — your GPU, your cluster, or a frontier API —
enforces the decision, executes it, and records it.
</p>

<p class="dg-hero__meta">an-NO-na · Rome's grain administration — sourcing, routing, and the record of both</p>
</div>

```bash
git clone git@github.com:Akaion-repos/annona.git
cd annona && make setup
make demo      # a real agentic run: no credentials, no network
```

## Why Rome kept its own grain

Agentic AI asks organisations to hand their internal systems to a remote model.
For a law firm, a clinic, or an engineering practice, that trade is not available
— the data is privileged by law.

The usual answers are *powerful but not sovereign* (cloud copilots) or *sovereign
but useless* (a local chatbot with access to nothing). Annona is the third
option: the model may be remote, the **execution and the data are not** — and
which of the two happens is decided per step, from policy, and written down.

The *cura annonae* was the office that kept Rome fed. It decided where grain was
sourced, which route it took, which granary held it and who received it, and it
kept the record — because a republic cannot outsource what it cannot live
without. Compute is now that input, and that is the vocabulary:

<div class="dg-terms" markdown="1">
<div class="dg-term"><div class="dg-term__name">placement</div><div class="dg-term__desc">where a step runs: local GPU, private cluster, frontier API</div></div>
<div class="dg-term"><div class="dg-term__name">clearance</div><div class="dg-term__desc">the decision on a tool call, an egress, or a placement</div></div>
<div class="dg-term"><div class="dg-term__name">ledger</div><div class="dg-term__desc">the hash-chained record of every decision</div></div>
<div class="dg-term"><div class="dg-term__name">held</div><div class="dg-term__desc">a call the policy refused — never quietly rerouted</div></div>
</div>

## What a run looks like

`make demo` drives a **real agentic loop** — real tool execution against real
files, real policy checks — from a scripted backend, so it needs no API key and
opens no socket.

```
1 · a task the policy permits
  1. ok      explorer         {'operation': 'map', 'path': '…/documents'}
  2. ok      document_reader  {'path': '…/reports/q1_report.txt'}
  answer     Q1 2026: 142 open matters, 98 closed, EUR 412,000 …

2 · a task the policy refuses
  1. held    filesystem       {'operation': 'read', 'path': '~/.ssh/id_rsa'}
     → {'error': 'Permission denied for tool: filesystem'}
```

Nothing left the process. That is the product in one screen.

## Where it runs

Three topologies, **one binary, one release**. They differ in configuration —
which backends are registered and what the policy permits — never in code. A fork
per deployment is how sovereignty claims rot, so there isn't one.

| | **Detached** | **Attached** | **Appliance** |
|---|---|---|---|
| Hardware | laptop, Mac mini | any | DGX-class, or EU colocation |
| Control plane | none | Agents Studio, outbound-only | Agents Studio |
| Inference | local only | local + remote, routed | local, remote by exception |
| Network | may be air-gapped | outbound 443 only | outbound 443 only |

Both ends are covered by tests: `tests/test_e2e_topologies.py` runs the detached
path with no network at all, and the attached path against a live HTTP server
implementing the documented three-endpoint contract.

## Start here

<div class="grid cards" markdown>

- **[Install](getting-started/install.md)** — native bundle or from source
- **[Quickstart](getting-started/quickstart.md)** — first vault, first run
- **[High-level design](design/hld.md)** — placement, the prefect, the DGX appliance
- **[Architecture as built](design/architecture.md)** — what the code does today
- **[Sovereign runtime](design/sovereign-runtime.md)** — where it is going, and the threat model
- **[Research](research/index.md)** — what we are trying to prove, and what is not built
- **[Decisions](adr/index.md)** — why it is shaped this way

</div>

## Honest status

This project publishes its gaps. The claim is *measurable* sovereignty, and a
claim without a measurement is marketing.

| Gap | State |
|---|---|
| Policy is default-allow — an unknown tool is permitted | <span class="dg-pill dg-pill--open">open</span> |
| Nothing classifies or gates what leaves toward a model provider | <span class="dg-pill dg-pill--open">open</span> |
| "Your data does not leave" is an argument, not a measured number | <span class="dg-pill dg-pill--open">open</span> |
| The ledger is a log file, not a verifiable artefact | <span class="dg-pill dg-pill--open">open</span> |
| Placement is a config line, not a per-step policy decision | <span class="dg-pill dg-pill--open">open</span> |
| Fully local mode can talk, but not act | <span class="dg-pill dg-pill--open">open</span> |
| One agentic loop, provider-agnostic, enforced in CI | <span class="dg-pill dg-pill--cleared">done</span> |
| Both topologies covered end to end | <span class="dg-pill dg-pill--cleared">done</span> |

Each open item has a metric and a phase attached — see
[Research](research/index.md).

!!! warning "Remote backends currently send the whole transcript"
    With `ai.provider: akaion` or `anthropic`, tool results — the contents of
    every file the agent read — are sent on the following turn. Local tool
    execution is not local data handling. This is asserted by a test so it cannot
    change unnoticed, and closing it is Phase 1.

---

Annona is developed by **[Akaion AI Lab](https://akaion.com)** and released under
Apache-2.0. It builds on [datapizza-ai](https://github.com/datapizza-labs/datapizza-ai)
(MIT) — see [ADR 0001](adr/0001-adopt-datapizza-ai.md).
