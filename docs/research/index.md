# Research

Annona is the reference implementation for work at **Akaion AI Lab** on one
claim: *sovereignty should be measurable*.

"Your data stays inside" is an architectural argument. Architectural arguments
are unfalsifiable, which is why every vendor makes one. We are trying to replace
it with three things a customer can check: **a measured leak rate**, **a
cost/privacy frontier**, and **a command they run themselves**.

This document states what we are trying to prove, how we intend to measure it,
and what is not built yet. Negative results are published here too.

---

## § Enforcement — from advisory filter to policy kernel

**Status:** partially implemented, wrong default.

`runner/permissions/manager.py` checks filesystem, shell, network and system
access on every tool call. Two properties make it advisory rather than
enforcing:

- `check_tool_permission()` returns `True` for any tool name it does not
  recognise (`manager.py:76`). New tools are permitted until someone adds a
  branch.
- An empty allow-list in a category means *allow everything* in that category.
  The safe configuration is the verbose one, which is backwards.

**Target.** Default-deny, capability-based: a tool executes only against an
explicitly granted capability, and an unknown tool is a denied tool. Denials are
first-class events in the trace, not warnings in a log file.

**Why it is research and not a patch.** Default-deny is trivial to write and hard
to ship: it breaks every existing configuration and turns silent over-permission
into visible friction. The open question is the *granularity* at which policy is
both expressive enough to be useful and simple enough that a practice's IT
consultant can audit it in an afternoon. We intend to publish the policy DSL and
the failure modes we hit, including the ones that forced us to loosen it.

**Metric.** Attack success rate on a prompt-injection corpus: documents in the
vault that instruct the agent to exfiltrate or destroy, measured as *fraction
that produce a policy-violating tool call*. Baselines: no policy, current
advisory policy, default-deny policy.

---

## § PCR — Privacy-Constrained Routing

**Status:** not implemented. This is the primary research contribution.

Formally: an agent plan is a DAG of steps. Each step's inputs carry sensitivity
labels estimated by a local classifier. Choose an execution plan — which model,
executed where — that minimises cost and latency **subject to a hard
constraint**: no token of class ≥ S crosses the perimeter.

It is constrained scheduling where the constraint is itself estimated by a model.
That is what makes it a research problem rather than a configuration screen: **the
constraint can be violated by classifier error, and nobody measures that error.**

Interesting cases, in increasing difficulty:

1. **Uniformly generic step** — route to the best/cheapest remote model. Easy.
2. **Uniformly sensitive step** — must stay local. Costs quality; how much is an
   empirical question (see § Local agentic loop).
3. **Mixed step** — a document that is 5% privileged and 95% boilerplate. All-local
   pays quality for nothing; all-remote violates. This is where the value is, and
   where § Redacted speculative execution applies.

**Metrics.**

- Pareto frontier of **€ / latency vs residual leak rate**, against two baselines:
  all-local (safe, slower, lower quality) and all-remote (violating).
- Fraction of tokens retained locally at equal task quality.
- Quality delta on the vertical benchmark, per data class.

**Precondition.** PCR needs exactly one place in the codebase where content can
leave the perimeter. Today there are three (one per provider loop) — see
[Sovereign runtime](../design/sovereign-runtime.md). The loop
unification is not refactoring hygiene; it is the precondition for this work.

---

## § Leak canary — measuring what actually escapes

**Status:** not implemented. Highest priority: it is both the metric for PCR and
the strongest demonstration we can give a customer.

Seed the corpus with synthetic but realistic identifiers that exist nowhere else
— IBANs, tax codes, names, case numbers — with known ground truth. Run real
workloads. Count how many canaries appear in outbound traffic.

The output is a **measured leak rate**, not a promise. To our knowledge nobody
publishes measured leak rates for hybrid local/remote agent stacks; the claim is
always architectural.

Two things this gives us that an architecture diagram cannot:

- A regression test. A leak rate is a number that can go up in a pull request.
- A sales artifact. Zero canaries out of fifty thousand requests, on a dashboard,
  in a room full of lawyers.

**Design notes.** Canaries must be realistic enough to be classified the same way
real data is (a canary the classifier finds *easier* than real data inflates the
result), and unique enough to be detected with certainty in egress. Both
properties are in tension. We will publish the generator and the tension.

---

## § Trace-as-proof — an audit trail you can verify

**Status:** not implemented. Low cost, high commercial return.

The audit trail should not be a log file but a verifiable artifact: a hash chain,
signed by Annona's key, recording for each step the declared data
classification and the egress ledger.

Ship `akaion-verify` as an open tool that anyone runs over a trace and gets a
yes/no on *"no class-3 data left this perimeter during period X"*.

This turns "don't trust us, verify" from a slogan into a shell command. It is
also the artifact that aligns with AI Act logging obligations — and a published
spec, unlike a feature, sets a standard rather than competing inside one.

**Secondary use.** A complete trace makes deterministic replay possible, which
makes agent regression testing possible. See Lab Note 12.

---

## § Local agentic loop — can the appliance actually act?

**Status:** not implemented for local models. Design in
[Sovereign runtime](../design/sovereign-runtime.md).

`reason_and_execute()` (`runner/ai_client.py:376-381`) implements tool use for
`akaion` (a cloud proxy) and `anthropic` only. With `ai.provider: local` the loop
degrades to plain chat completion: **fully local mode can talk, but not act.**

There is a second, sharper problem. With `provider: akaion` the entire `messages`
array — including `tool_result` blocks carrying the contents of every file the
agent read — is sent to `/runner/agent/turn` on each iteration. Tools execute
locally; the documents travel. Local execution of tools is not local execution of
the workload, and the distinction has to be stated plainly rather than blurred.

**Open questions.**

- How small can a local model be and still complete each real task class? The
  answer is a routing table, and it is the input to both PCR and appliance
  sizing (Lab Note 08).
- Does constrained decoding (grammar-forced, schema-valid tool calls) close the
  reliability gap between an 8B local model and a frontier model on tool use? Our
  hypothesis is that most local-model tool-use failure is malformed arguments
  rather than wrong intent — if so, grammars convert a quality problem into a
  solved problem.
- Does plan-then-execute beat free-form ReAct on small models? Fewer degrees of
  freedom should mean less drift over a ten-step horizon.

---

## § Redacted speculative execution

**Status:** exploratory. High risk, high ceiling.

For the mixed-sensitivity step: the local model drafts and redacts, the remote
model verifies and expands **only the non-sensitive spans**, the local model
stitches. It is speculative decoding across a trust boundary — normally draft and
verifier share a machine, which is why nobody has studied it with an egress
constraint in the middle.

**Metrics.** Span acceptance rate; quality vs full-remote; tokens emitted vs
full-remote; added latency.

---

## Lab Notes

Small empirical results, published on a cadence. One question, one measurement,
one artifact, one to two weeks. Every note is an optimisation of something we
already run in production — that is what makes them defensible and hard to
reproduce from the outside.

| # | Question | Metric | Artifact |
|---|---|---|---|
| 01 | Do telegraphic ("caveman") prompts hold up for **tool calling**, or do they degrade argument fidelity and schema adherence? | tokens saved vs schema-violation rate, per model | `caveman-tools` + per-model table |
| 02 | How far can **MCP tool descriptions** be compressed before tool selection collapses? | selection accuracy vs schema tokens, at growing N tools | tool-schema minifier |
| 03 | Past how many RAG chunks does quality **get worse**? | task success vs k, per model and context length | auto-k policy |
| 04 | Ablate the system prompts of the vertical agents: which sections are dead weight? | success with/without each section | prompt linter |
| 05 | What is **prefix-cache-aware prompt ordering** (stable → volatile) actually worth? | € and ms saved on real traffic | guidelines + middleware |
| 06 | **Speculative tool prefetch**: start executing the likely call while the model is still emitting | p50/p95 latency on booking flows | executor patch |
| 07 | **Barge-in thresholds** on 8 kHz Italian telephone audio | false-interrupt rate vs response latency | curve + config |
| 08 | For each real task class, what is the **smallest local model that passes**? | success threshold per family and quantisation | routing table → feeds PCR and appliance sizing |
| 09 | **8B × 3 attempts + verifier** or frontier × 1? | cost and quality on structured extraction | if it holds, it is what makes appliance economics work |
| 10 | **Embedding quantisation** (int8 / binary) on a real corpus | recall@k lost vs memory and latency gained | larger corpora on the same appliance |
| 11 | When does **summarising** conversation history beat truncating it? | multi-turn task success vs context strategy | compaction policy |
| 12 | How often do identical agent runs **diverge**, and why — sampling or tool nondeterminism? | divergence rate by cause | replay harness |

---

## Programme order

Dependency order, not preference order:

1. **Loop unification** ([Sovereign runtime](../design/sovereign-runtime.md)) — one place where content can leave. Precondition for 2, 3 and 4.
2. **Leak canary** — the metric. Without it, PCR is an assertion, exactly like today.
3. **Lab Note 08** — the routing table PCR decides against, and the sizing numbers.
4. **PCR**, then **trace-as-proof**, then **redacted speculative execution**.

Enforcement (§1) can proceed in parallel; it does not depend on the loop work.
