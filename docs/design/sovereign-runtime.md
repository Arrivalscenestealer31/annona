# Sovereign Agent Runtime — Design

Design document for the Runner's execution core. Target state: **the agentic loop
runs inside the perimeter, and a model — local or remote — is an inference
endpoint with no authority over control flow or egress.**

Status: proposed. Nothing here is implemented yet.

Audience: someone who forks this repository and wants to be convinced the
boundary holds before putting it on their own hardware.

---

## 1. Scope

**In scope.** How a task becomes tool calls; where inference happens; what may
leave the perimeter and how that is decided, enforced and recorded.

**Out of scope.** Plan authoring (Agents Studio), vault storage
(`runner/brain/`), the desktop shell (`ui/`).

**Non-goals, stated so they are not mistaken for oversights.**

- *Not* a replacement for frontier models. All-local pays quality for data that
  did not need protecting; § 7 exists precisely because that trade should be
  measured rather than assumed.
- *Not* a general agent framework. We depend on one (§ 8) instead of writing a
  fourth.
- *Not* protection against a malicious operator. The perimeter defends against a
  misbehaving *model*, not against the person holding root (§ 6).

---

## 2. Three topologies, one binary

The same artifact must run detached on a Mac mini in a cupboard, attached to a
cloud control plane, or on a DGX-class appliance serving a whole practice. These
are **configuration, not builds** — one codebase, one release, no forks per
deployment. That is a hard architectural constraint, because a fork per topology
is how sovereignty claims rot.

| | **Detached** | **Attached** | **Appliance** |
|---|---|---|---|
| Hardware | laptop, Mac mini | any | DGX-class, or EU colocation |
| Control plane | none — local plans and CLI | Agents Studio (outbound-only) | Agents Studio |
| Inference | local runtime only | local + remote, routed | local (vLLM), remote by exception |
| Users | one | one | many, per-user policy |
| Network | may be fully air-gapped | outbound 443 only | outbound 443 only |
| Egress class ceiling | none permitted | policy-defined | policy-defined |

What differs between them: which backends get registered, and the policy
document. Nothing else. A reviewer checks this by diffing two config files, not
two branches.

---

## 3. Layers and the dependency rule

```
┌──────────────────────────────────────────────────────────┐
│  L4  adapters      CLI · local_api · Tauri UI · poller    │
├──────────────────────────────────────────────────────────┤
│  L3  orchestration agent loop · planner · verifier        │
├──────────────────────────────────────────────────────────┤
│  L2  perimeter      policy kernel · classifier · egress    │
│                     gate · trace  ◀── the only way out     │
├──────────────────────────────────────────────────────────┤
│  L1  capability     tools · inference backends · vault     │
├──────────────────────────────────────────────────────────┤
│  L0  kernel         types · errors · config · clock        │
└──────────────────────────────────────────────────────────┘
```

**Dependency rule: imports point inward and downward only.** L3 may not import
from L1 directly; it reaches capabilities through L2. This is not style — it is
what makes § 4 mechanically checkable. A CI job enforces it (`import-linter`),
and a failing check is a boundary regression, not a lint warning.

---

## 4. The formal core: the perimeter as total mediator

### 4.1 The property

> **P1 (Inference egress totality).** Every byte of task-derived content that
> reaches a non-local inference backend passes through exactly one call site:
> `Perimeter.release()`.

P1 is what makes a measured leak rate meaningful, a hash-chained trace complete,
and privacy-constrained routing implementable. Its absence is the single biggest
defect of the current code, which has three independent egress sites — one per
provider loop — so no control can be total.

### 4.2 How it is enforced structurally, not by discipline

Four mechanisms, deliberately redundant:

1. **The loop cannot hold a raw client.** The orchestrator's constructor accepts
   `SealedClient`, never `Client`. There is exactly one way to obtain one:

   ```python
   sealed = Perimeter.seal(client, policy, classifier, trace)
   agent  = AgentLoop(client=sealed, tools=...)   # type: SealedClient
   ```

2. **`SealedClient` is not constructible directly.** Its `__init__` requires a
   witness object that only `Perimeter.seal` can mint. Constructing one by hand
   raises at import-time review and at runtime.

3. **L3 may not import a provider.** `import-linter` forbids
   `runner.agent.* → runner.backends.*`. A new provider that skips the gate
   cannot be wired in without failing CI.

4. **The gate is on the inference call, not on the loop step.** Wrapping the
   *client* rather than hooking the *step* means a control-flow bug in the loop
   cannot route around it: there is no code path to a remote model that does not
   traverse the wrapper.

Point 4 is the reason we wrap rather than use the framework's `before_step` /
`after_step` hooks (§ 8). Step hooks are the right place for observability and
the wrong place for a security boundary — they observe a decision that has
already been made.

### 4.3 Where P1 does not hold — stated plainly

P1 covers the **inference channel**. There is a second channel: tools that can
themselves reach the network.

> **A `shell` tool with unrestricted commands voids any egress proof.** A model
> that can run `curl` needs no help from the inference path. So does a `browser`
> tool with arbitrary URLs.

This is not a hole to paper over; it is a constraint on what a verifiable profile
can contain:

- **P2 (Tool egress).** Network-capable tools are gated by the same policy, with
  a domain allow-list, and every attempt is recorded whether allowed or denied.
- **P3 (Profile honesty).** A profile that enables unrestricted shell is marked
  `unverifiable` in the trace header, and `akaion-verify` refuses to issue a
  clean bill for it. The appliance profile ships shell disabled by default;
  where it is enabled, it is allow-listed to binaries with no network capability.

A claim we can defend is worth more than a claim that covers more.

### 4.4 Invariants

| | Invariant |
|---|---|
| **I1** | Default-deny. An unknown tool is a denied tool; an empty allow-list grants nothing. (Current code does the opposite — `permissions/manager.py:76`.) |
| **I2** | Egress totality on the inference channel (P1). |
| **I3** | Tool network egress allow-listed; unverifiable profiles labelled as such (P2, P3). |
| **I4** | The trace is append-only and hash-chained, with one entry per decision — **denials included**. A missing entry is detectable; a rewritten one is not verifiable. |
| **I5** | No ambient credentials. Cloud tokens live in the perimeter and are unreachable from tool code; a tool cannot authenticate outward on its own. |
| **I6** | Config is data. The three topologies of § 2 differ only in configuration. |
| **I7** | Fail closed. A classifier error, an unreachable policy, a corrupt trace chain → the step fails. Never "proceed and log". |

I7 deserves emphasis because it is the one that costs. Failing closed on a
classifier timeout means the agent stops working when a local model is slow. That
is the correct trade for privileged data and it will generate support tickets.

---

## 5. Data classification and the egress contract

Classes are ordinal and few, because a taxonomy nobody can apply is a taxonomy
nobody applies:

| Class | Meaning | Default routing |
|---|---|---|
| `C0` public | Published or trivially public | any backend |
| `C1` internal | Business content, not personal | remote permitted if policy allows |
| `C2` personal | Personal data (GDPR) | local unless explicitly permitted |
| `C3` privileged | Professional secrecy, health, legal | **local only, never releasable** |

`Perimeter.release(payload, backend)` is total in the mathematical sense too — it
returns a decision for every input:

```python
Release = Allowed(payload) | Redacted(payload, spans) | Denied(reason, class)
```

`Redacted` is where § 7's mixed-sensitivity work lands. Until it exists, the
implementation returns only `Allowed` or `Denied`, and a mixed step is `Denied`.
Starting conservative is a decision, not a limitation: it means the first
measured leak rate is a real baseline rather than a preview.

---

## 6. Threat model

**Defended against.** A model that has read a prompt-injecting document and tries
to exfiltrate or destroy; an over-broad plan from the control plane; a compromised
control plane attempting to raise its own privileges (policy is local, and the
plane cannot edit it); accidental egress from a misconfigured provider.

**Not defended against.** Root on the box; a malicious operator; a model
extracting data through an allow-listed tool's legitimate output channel;
side-channels (timing, token counts) against a remote backend. Each is listed so
a customer's auditor can stop looking for a claim we did not make.

**Note on the control plane.** The plane says *what*; the perimeter says *whether*.
This asymmetry is the reason the plane can stay proprietary without weakening the
sovereignty claim — and the reason the perimeter cannot.

---

## 7. Local inference: tiers and capabilities

Small models do not fail at *choosing* a tool. They fail at *emitting valid
arguments*. Three tiers, selected by probe, best first.

**Tier 1 — native tool calling.** Ollama and vLLM expose OpenAI-style `tools` for
models trained for it. Cheapest when available; reliability is measured, not
trusted.

**Tier 2 — constrained decoding.** Compile each tool's JSON Schema into a grammar
and constrain generation: llama.cpp GBNF, vLLM `guided_json`, Ollama `format`.
The model becomes **structurally incapable** of emitting a malformed call.
Schema violations go to zero by construction; what remains is semantic error —
a smaller, better-behaved failure class.

> Hypothesis worth publishing: *most local-model tool-use failure is malformed
> arguments, not wrong intent.* If it holds, grammars turn the 8B-vs-frontier
> tool-use gap from a quality problem into a solved one. This is the strongest
> technical claim in the programme.

**Tier 3 — ReAct text protocol.** Tolerant parser plus one repair prompt. Lossy;
kept so an unsupported model degrades rather than fails, and instrumented so we
can see how often we land here.

```python
@dataclass(frozen=True)
class Capabilities:
    native_tools: bool
    grammar: Literal["none", "json_schema", "gbnf", "guided"]
    parallel_tool_calls: bool
    context_window: int
    is_local: bool          # read by the perimeter, not by the loop
```

Probed once at startup against the live endpoint, cached in
`~/.akaion/backend-caps.json`, invalidated on model or endpoint change. Probing
beats a hardcoded matrix: the matrix is wrong within a month.

**Runtime targets.** Ollama for the laptop and first run; llama.cpp server for
small on-prem boxes and Apple silicon (best-in-class GBNF); vLLM for the
appliance (guided decoding, batching, throughput). All three speak
OpenAI-compatible HTTP; differences live in `Capabilities`, never in branches.

### 7.2 Loop quality on small models

A frontier model tolerates free-form ReAct over ten steps; an 8B model drifts —
repeats calls, forgets the goal, declares success early. Three mitigations, each
also a measurable result:

- **Plan-then-execute.** One planning call emits a typed step list; the loop
  executes with per-step verification and replans only on failure. Fewer degrees
  of freedom per step, less drift over the horizon.
- **Verifier pass.** A cheap second local call judges whether a step satisfied
  its intent before proceeding (Lab Note 09).
- **Progress guard.** Iteration budget plus a no-progress detector — repeated
  identical calls, no new information — that stops instead of burning budget.
  Cheap, and it is the difference between a demo and something left running in a
  practice.

---

## 8. The datapizza seam

We build on [`datapizza-ai`](https://github.com/datapizza-labs/datapizza-ai)
(MIT, Datapizza Labs) rather than writing a fourth agent framework. Its core
already provides the canonical vocabulary this design needs, and adopting an
Italian open framework is coherent with what we are trying to be — an ecosystem
participant, not a proprietor.

**What we depend on** — `datapizza-ai-core`, the most stable surface:

| Their component | Our use |
|---|---|
| `datapizza.type` — `TextBlock`, `FunctionCallBlock`, `FunctionCallResultBlock`, `StructuredBlock` | the canonical message vocabulary; provider translation stays in their clients (`ROLE.anthropic_role`, `google_role`) |
| `datapizza.core.clients.Client` | the interface our `SealedClient` wraps |
| `datapizza.clients.openai_like` | local runtimes: takes `base_url`, forwards `**kwargs` to `chat.completions.create`, so `guided_json` / `grammar` pass through unmodified |
| `datapizza.tools.Tool` | provider-agnostic tool schemas |
| `datapizza.agents.Agent` — `max_steps`, `Plan`, `before_step`/`after_step` | the loop and planning skeleton |
| `datapizza.memory`, `.cache`, `.tracing` | conversation state, replay keys, observability spans |
| `datapizza-ai-eval` | harness substrate for the Lab Notes |

**What we own** — and it is precisely the part that does not exist anywhere:

1. **`SealedClient` + `Perimeter`** — policy kernel, classifier, egress gate,
   fail-closed semantics. Wrapping their `Client` rather than using step hooks,
   for the reason in § 4.2.
2. **Constrained-decoding clients + capability probe** — GBNF and guided-decoding
   backends with schema→grammar compilation.
3. **Tamper-evident trace** — hash-chained and signed. Their tracing answers
   "what happened?"; ours has to answer "can you prove what did not?".
4. **The measurement harness** — leak canary, routing table, the frontier.

**What we upstream.** The grammar clients and the capability probe are generally
useful and carry no competitive value: offer them as
`datapizza-ai-clients-llamacpp` and `-vllm`. Contributing the local-inference
layer to the Italian framework, while keeping the perimeter here, is the right
split on both engineering and narrative grounds.

**Dependency risk, honestly.** datapizza-ai is young (public since October 2025,
~2.2k stars, ~212 commits). Mitigations: depend on `-core` only, pin exact
versions, keep our loop and perimeter ours, and confine their types to L0/L1 —
an adapter in L1 means a fork or a replacement touches one layer. The MIT notice
goes in `NOTICE`.

---

## 9. Module layout

```
runner/
├── kernel/          L0  types · errors · config · clock (no I/O)
├── capability/      L1
│   ├── tools/           filesystem · shell · browser · documents · explorer
│   └── backends/        ollama · llamacpp · vllm · anthropic · akaion · openai
├── perimeter/       L2  ◀── the boundary
│   ├── policy.py        default-deny capability kernel
│   ├── classify.py      C0–C3 labelling
│   ├── gate.py          Perimeter.seal() · release() → Allowed|Redacted|Denied
│   ├── sealed.py        SealedClient (unconstructible without a witness)
│   └── trace.py         append-only hash chain, signed
├── agent/           L3  loop · planner · verifier · progress guard
├── adapters/        L4  cli · local_api · poller · sync
└── verify/              akaion-verify — ships as a standalone entry point
```

`akaion-verify` is a separate entry point on purpose: a verifier that ships
inside the thing it verifies is worth less, and a customer's auditor should be
able to run it against a trace file on a different machine.

---

## 10. Configuration — one axis

```yaml
profile: appliance          # detached | attached | appliance
perimeter:
  max_egress_class: C1      # C0 in detached; nothing above C1 ever leaves
  fail_closed: true         # I7 — do not set false in production
  classifier: local:granite-guardian    # or rules-only
policy:
  default: deny             # I1
  grants:
    - tool: read_file
      paths: [~/Studio/pratiche]
    - tool: shell
      commands: [ls, git]
      network: false        # P3: keeps the profile verifiable
inference:
  local:
    runtime: vllm           # ollama | llamacpp | vllm
    endpoint: http://127.0.0.1:8000
    model: qwen3-14b-instruct
  remote:
    backend: akaion         # omit entirely in detached
trace:
  path: ~/.akaion/trace/
  sign: true
```

`profile` sets defaults; every key stays individually overridable. A reviewer
reads one file to know what this box is allowed to do.

---

## 11. Trace format

One JSON object per line, each carrying `prev_hash` over the canonical encoding
of the previous entry. The header records profile, policy digest, backend
identities and capabilities, and whether the profile is `verifiable`.

Entry kinds: `task_start`, `plan`, `classify`, `tool_call`, `tool_result`,
`policy_decision` (allow **and** deny), `egress` (payload digest, class, backend,
decision), `step_verdict`, `task_end`.

Egress entries record a **digest, never the payload** — a trace that leaks what
it exists to protect would be a fine joke at our expense.

`akaion-verify` checks chain continuity, signature validity, that no `egress`
entry exceeds `max_egress_class`, that every `tool_call` has a matching
`policy_decision`, and that the profile is `verifiable`. Output: a verdict and
the entries that produced it.

---

## 12. Phases and weight

One engineer, calendar time including tests. Adopting datapizza removes most of
what was Phase 0-1 in the previous revision of this document.

| Phase | Work | Size | Risk |
|---|---|---|---|
| **0** ✅ | Adopt `datapizza-ai-core`; L0 kernel with ports; L1 adapters for akaion, anthropic and offline echo; **one loop** in L3; import contracts in CI. No behaviour change. | done | — |
| **1** | `Perimeter` + `SealedClient` + policy kernel default-deny. One egress site, everything routed through it. | 1 w | medium — inverting the permission default breaks existing configs by design |
| **2** | Local backends with tool use: Ollama T1, llama.cpp T2 with schema→GBNF, capability probe, T3 fallback. **Fully local agentic execution lands here.** | 1–1.5 w | medium-high — where model reality bites |
| **3** | Trace: hash chain, signing, `akaion-verify` as a separate entry point. | 4-5 d | low — one call site by now |
| **4** | vLLM backend, plan-then-execute, verifier, progress guard, leak-canary harness on `datapizza-ai-eval`. | 2 w | medium |

**≈ 5 weeks** to fully local agentic execution with a verifiable trace and a
measurement harness behind it. Phase 0 is complete — see
[ADR 0002](../adr/0002-unify-the-agentic-loop.md) and the
[architecture as built](architecture.md). It came in at the estimate and delivered
more than planned: the loop unification itself, which the original plan put in
Phase 1, landed with it, because the ports made it the cheaper option.

Phase 1 now starts from a codebase where there is exactly one call site to wrap.

Order matters more than speed: Phase 2 makes the pitch's central claim *true*,
Phase 3 makes it *provable*. If the calendar has to be cut, cut Phase 4 — an
unprovable claim is the position we are in today.

**Rejected alternative.** Adding a fourth `_agentic_loop_local` beside the
existing three ships local tool use in two days. It also makes four egress sites,
so every control above has to be built and audited four times, and P1 becomes
unstateable. It buys a demo and mortgages the programme.

---

## 13. Open design questions

Recorded rather than hidden, because a fork deserves to know where the design is
uncertain:

1. **Classification granularity.** Per-document, per-span, or per-field? Spans
   are what `Redacted` needs and the most expensive to get right.
2. **Who classifies the classifier?** `fail_closed` makes a local classifier a
   hard dependency in the hot path. Rules-only fallback, or refuse to run?
3. **Trace signing key custody.** A key on the same box a malicious operator
   controls proves less. TPM/Secure Enclave, or an external notary — the honest
   answer may be "this proves integrity against tampering, not against the
   operator" (§ 6).
4. **Multi-user policy on the appliance.** Per-user perimeters in one process, or
   one process per user? Isolation argues for the second, cost for the first.
5. **Framework coupling.** If datapizza's `Agent` proves too opinionated for
   plan-then-execute plus a progress guard, do we keep their types and write our
   own loop? Probably yes, and the L1 adapter is what makes that cheap.
