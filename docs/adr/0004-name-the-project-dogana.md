# 0004 — Name the project Dogana

- **Status:** Accepted
- **Date:** 2026-07-28
- **Deciders:** Akaion AI Lab

## Context

"Akaion Runner" describes an org chart, not a product. It says the thing belongs
to a vendor and runs something, which is exactly the impression an open-source
project promising *sovereignty* must avoid: the pitch is "don't trust us, verify
it yourself", and a name that leads with the vendor undercuts it before anyone
reads a line of code.

The name also had to survive being said out loud in a room of engineers who did
not build it.

## Decision

**Dogana** — Italian for *customs*. Pronounced doh-GAH-nah.

A customs post is the product, literally: everything crossing the border is
declared, checked against the rules, and either cleared or held, and a stamped
record survives the crossing. That is the perimeter, the policy gate, and the
trace, in one word that a non-technical buyer already understands.

### It brings a vocabulary, which is the real reason

A good name gives the rest of the system its words. This one does:

| Term | What it names |
|---|---|
| **declaration** | what a step states it is about to send outward |
| **clearance** | the gate's decision on a tool call or an egress |
| **manifest** | the trace — an ordered, verifiable record of every crossing |
| **held** | a call the policy refused |
| **green lane** | a path pre-cleared as low-sensitivity, no inspection needed |

"The manifest shows three crossings, two cleared, one held" is a sentence a
lawyer and a kernel engineer both parse correctly. That is worth more than a
clever logo.

Italian is deliberate: it is coherent with an Italian lab building on an Italian
framework ([ADR 0001](0001-adopt-datapizza-ai.md)), and it is pronounceable
everywhere.

### Scope of the rename

Applied now:

- `runner/branding.py` — a single source of truth for the name, tagline and
  vocabulary. Renaming again is one edit.
- `dogana` installed as an **equal console-script alias**; `akaion` still works.
- CLI help, documentation site, README.

Deliberately *not* applied:

- The Python package stays `runner`. Renaming it churns every import and every
  test for no user-visible gain.
- The repository stays `akaion-app-runner` until the project is public; renaming
  it breaks clone URLs and the release workflow's asset names.
- The `akaion` command is not removed. Deleting a command people have in their
  shell history to make a naming change tidy is a bad trade.

## Alternatives considered

**Airlock.** The obvious metaphor, and taken three times over in exactly this
space — `agent-airlock`, `airlock-dev/airlock` and the project formerly called
MCP-Airlock are all 2026 AI-agent security tools. Being the fourth Airlock is
worse than being nobody.

**Bastion, Boundary, Sentry, Checkpoint.** All taken by established
infrastructure or security products. Legally awkward at best, invisible in search
at worst.

**Perimeter.** Accurate, dull, unsearchable.

**Limes** — the fortified Roman frontier, watchtowers and records included.
Historically perfect and phonetically unfortunate: English speakers read the
plural of a citrus fruit.

**Membrane.** Precise about selective permeability, too soft for something whose
job is to refuse.

## Consequences

**Good.** A name that carries the concept, a vocabulary that makes the docs
easier to write, and no collision in the space it competes in. The project reads
as a project rather than as a vendor's component, which is the point of open
core.

**Bad, and accepted.** Two names in circulation during the transition — the
command is `akaion`, the project is Dogana — which is mildly confusing until the
repository goes public and the primary command follows. The alias keeps that from
being a breaking change whenever it happens.

**Neutral.** "Dogana" is unfamiliar to non-Italian speakers on first hearing.
Every strong project name was; the tagline does the explaining.
