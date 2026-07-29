---
hide:
  - navigation
---

<div class="dg-hero" markdown="1">
<span class="dg-hero__eyebrow">Akaion AI Lab · Apache-2.0</span>

<h1 class="dg-hero__title">Do<span class="dg-hero__stamp">gana</span></h1>

<p class="dg-hero__tagline">Nothing crosses undeclared.</p>

<p class="dg-hero__sub">
The perimeter for AI agents. Dogana runs agent plans inside your infrastructure,
checks every tool call against your policy, and keeps a record of what left the
building — and what did not.
</p>

<p class="dg-hero__meta">doh-GAH-nah · Italian for <em>customs</em></p>
</div>

```bash
git clone git@github.com:Akaion-repos/akaion-app-runner.git
cd akaion-app-runner && make setup
make demo      # a real agentic run: no credentials, no network
```

## Why a customs post

Agentic AI asks organisations to hand their internal systems to a remote model.
For a law firm, a clinic, or an engineering practice, that trade is not available
— the data is privileged by law.

The usual answers are *powerful but not sovereign* (cloud copilots) or *sovereign
but useless* (a local chatbot with access to nothing). Dogana is the third
option: the model may be remote, the **execution and the data are not**.

A border post is the whole idea. Goods crossing it are declared, checked against
the rules, and either cleared or held — and a stamped record survives the
crossing. So that is the vocabulary:

<div class="dg-terms" markdown="1">
<div class="dg-term"><div class="dg-term__name">declaration</div><div class="dg-term__desc">what a step states it is about to send outward</div></div>
<div class="dg-term"><div class="dg-term__name">clearance</div><div class="dg-term__desc">the gate's decision on a tool call or an egress</div></div>
<div class="dg-term"><div class="dg-term__name">manifest</div><div class="dg-term__desc">the trace: a verifiable record of every crossing</div></div>
<div class="dg-term"><div class="dg-term__name">held</div><div class="dg-term__desc">a call the policy refused</div></div>
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
| The manifest is a log file, not a verifiable artefact | <span class="dg-pill dg-pill--open">open</span> |
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

Dogana is developed by **[Akaion AI Lab](https://akaion.com)** and released under
Apache-2.0. It builds on [datapizza-ai](https://github.com/datapizza-labs/datapizza-ai)
(MIT) — see [ADR 0001](adr/0001-adopt-datapizza-ai.md).
