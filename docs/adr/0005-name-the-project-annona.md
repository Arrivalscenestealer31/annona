# 0005 — Name the project Annona

- **Status:** Accepted — supersedes [ADR 0004](0004-name-the-project-dogana.md)
- **Date:** 2026-07-30
- **Deciders:** Akaion AI Lab

## Context

[ADR 0004](0004-name-the-project-dogana.md) named the project **Dogana** —
customs — because the product was a *gate*: it inspected what an agent tried to
do and either cleared it or held it.

Two days of design later the object is bigger than its name. The thing we are
building does not only refuse; it **decides where work runs and then runs it**:
on a DGX in the customer's rack, on a private GPU cluster, or against a frontier
API — one decision per step, taken from policy, and recorded. A customs post
names the inspection. It names neither the supply decision that precedes it nor
the record that outlives it.

Renaming again is a cost we pay once, now, while the repository is still private.
Renaming after publication is a cost paid by every person who starred it.

## Decision

**Annona** — pronounced *an-NO-na*.

The *cura annonae* was the office that kept Rome fed. It decided where grain was
sourced — Sicily, Africa, Egypt — which route it took, which *horrea* stored it,
and who received it, and it kept the record. It was run by a prefect answering to
the emperor, and it existed for one reason: **a republic cannot outsource what it
cannot live without.** When the annona failed, the city rioted.

Compute is now that input. That is the whole product in one historical sentence,
and it is a sentence a CIO parses without a glossary.

### What the name buys

It is the only candidate that names *all three* parts of the object rather than
one: **sourcing** (which substrate), **routing** (placement), and the **record**.
"Customs" names the second; "archive" names the third; a fortress metaphor names
none of them.

The vocabulary carries over almost unchanged from ADR 0004, which is why this
rename is cheap rather than a reset:

| Term | What it names | Status |
|---|---|---|
| **placement** | *where* a step runs: local GPU, private cluster, frontier API | new — the concept the old name could not hold |
| **declaration** | what a step states it is about to do and send | kept |
| **clearance** | the decision on a tool call, an egress, or a placement | kept |
| **held** | a call, or a placement, the policy refused | kept |
| **manifest** | what a step is permitted to carry across | kept |
| **ledger** | the ordered, hash-chained record of every decision | was *manifest*, renamed for the split above |
| **green lane** | a path pre-cleared as low-sensitivity | kept |
| **prefect** | the component that issues clearances — *praefectus annonae* | new |
| **horreum** | the local store: vault and ledger, on the customer's disk | new |
| **ration** | a user's or an org's quota of remote capacity | new — the hook for credits |
| **brief** | the locally produced, cleared summary that may cross in place of the raw material | new |

"The ledger shows four steps: three cleared, one held; two placed locally, one on
the frontier under a brief" is a sentence a compliance officer and a kernel
engineer both parse correctly, which is the entire test.

### The category

Annona is described as a **sovereign execution kernel**, not a framework, not a
gateway. The word is load-bearing:

- an *agent framework* (datapizza-ai, LangGraph) decides **how you write** an
  agent — Annona builds on one rather than being one;
- an *AI gateway* (LiteLLM, Portkey, Envoy AI Gateway) decides **which endpoint a
  token stream goes to** — it never executes a tool, never touches a file, and
  has no opinion about where the *rest* of the work happens;
- a *kernel* mediates between something that wants to act and the resources it
  wants to act on. It grants capabilities, schedules placement, enforces
  isolation, and keeps the record. That is this project.

## Collision check

The rule from ADR 0004 stands: being the fourth *Airlock* is worse than being
nobody. Every finalist was checked against PyPI, the GitHub name index and the
AI/infrastructure product space before the decision, not after. Four registers
were searched — institutional Italian, Roman, Italic/Etruscan, and the playful
food register that `datapizza-ai` occupies.

| Candidate | Verdict | Evidence |
|---|---|---|
| **Annona** | **chosen** | PyPI free. GitHub quiet: 142 repositories, the largest a 46★ digital-humanities tool, none in this space. No product collision. |
| Fondaco | runner-up, rejected | Free, and a good story — the Venetian compound where foreign merchants had to trade under the city's ledger. It names containment only; placement has to be argued into it. |
| Pomerium | rejected | Rome's sacred boundary, where the applicable law changed at the line. Semantically perfect, and already a well-known open-source identity-aware proxy. |
| Groma | rejected | The instrument that decided where everything in a camp went. `FoundationVision/Groma` is a 585★ multimodal LLM. |
| Limen | rejected | `thecodearcher/limen`, 484★, *composable authentication for Go* — adjacent enough to confuse, popular enough to lose the search. |
| Varco | rejected | **NCSOFT VARCO** is a shipped LLM family. Direct collision inside the AI category. |
| Sovra | rejected | Four live AI entities, one selling itself as *Sovereign Operational Virtual Reasoning Architecture*. Unwinnable search. |
| Tular | rejected | Etruscan for the boundary stone marking a city's jurisdiction — the pre-Roman ancestor of the concept. PyPI taken. |
| Cardo · Cursus · Principia · Castellum · Horreum · Arx | rejected | PyPI taken, or buried under thousands of unrelated repositories. |
| Scolapasta | rejected, on purpose | Namespace almost virgin, and the only food word whose function *is* the product: what passes, passes. It wins on GitHub and loses in a public-sector tender, and this is sold into both. |
| Dogana | superseded | Good name for the gate we were building. Wrong scope for the kernel we are building. |

The one real cost, recorded so nobody rediscovers it: `annona.dev`, `annona.ai`
and `annona.io` are all registered. The GitHub organisation and the PyPI name are
free, documentation lives on GitHub Pages, and a domain can be bought or
prefixed; a taken package name can be neither.

## Scope of the rename

Applied now:

- `runner/branding.py` — the single source of truth, as designed in ADR 0004.
  This rename was one edit there plus the strings that quote it.
- `annona` becomes the primary console script; `dogana` and `akaion` stay as
  aliases. Nobody's shell history breaks.
- README, documentation site, package metadata and the PyPI distribution name.

Deliberately not applied:

- The Python package stays `runner`. Same reason as ADR 0004: churning every
  import buys nothing a user can see.
- The repository directory stays `akaion-app-runner` until the split-out repo is
  created. The public repository will be `Akaion-repos/annona`; that is a
  create, not a rename, so no clone URL breaks.

## Consequences

**Good.** The name covers the whole object — sourcing, placement, execution,
record — so the documentation stops fighting it, and it carries an argument for
sovereignty two thousand years older than the product. The vocabulary survives
the rename, so code and docs do not fork.

**Bad, and accepted.** Two renames in three days looks indecisive in the git log,
and the three obvious domains are gone. Both are paid once, and only by us; the
alternative is paying forever in every conversation where the name says
*inspection* and the product does *placement*.

**Neutral.** ADR 0004 stays in the tree. A decision record you delete when it is
overtaken is a press release, not a record.
