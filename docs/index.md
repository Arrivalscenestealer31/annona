---
hide:
  - navigation
  - toc
  - path
  - footer
---

<div class="an-hero" markdown="1">

<img class="an-hero__mascot" src="assets/annona-mascot-512.png" alt="Annona">

<h1 class="an-hero__title">Annona</h1>

<p class="an-hero__tagline">The sovereign execution kernel for AI agents</p>

<p class="an-hero__sub">
Every agent you deploy sends your material somewhere. Annona decides
<strong>where each step may run</strong> — your GPU, your cluster, or a frontier
API — enforces the decision, and writes it into a record you can verify.
</p>

<div class="an-stats" markdown="1">
<div class="an-stat"><b>per step</b><span>placement</span></div>
<div class="an-stat"><b>default</b><span>deny</span></div>
<div class="an-stat"><b>0</b><span>leak rate</span></div>
<div class="an-stat"><b>559</b><span>tests</span></div>
<div class="an-stat"><b>arm64</b><span>DGX-ready</span></div>
</div>

<p class="an-cta" markdown="1">
[⬇ Download the app](https://github.com/akaion-ai/annona/releases/latest){ .an-btn .an-btn--primary }
[GitHub](https://github.com/akaion-ai/annona){ .an-btn }
[Design of record](design/hld.md){ .an-btn }
</p>

<p class="an-hero__meta">Open source · Apache-2.0 · no telemetry · runs with no account · <em>an-NO-na</em>, the office that kept Rome fed</p>

</div>

## Get the desktop app

Ready to run, local by default: it registers nothing outside your machine until
you declare it yourself.

<div class="grid cards an-downloads" markdown>

-   :material-microsoft-windows: **Windows**

    ---

    Per-user installer (`.exe`). No admin rights.

    [Download .exe](https://github.com/akaion-ai/annona/releases/latest){ .an-btn .an-btn--primary }

-   :material-apple: **macOS**

    ---

    Apple Silicon and Intel (`.dmg`). Ad-hoc signed, not notarised during beta:
    drag to Applications, then **right-click the app → Open** the first time.
    [Why macOS asks](getting-started/macos-gatekeeper.md)

    [Download .dmg](https://github.com/akaion-ai/annona/releases/latest){ .an-btn .an-btn--primary }

-   :material-linux: **Linux**

    ---

    Portable AppImage (`chmod +x` and run), or `.deb`.

    [Download AppImage](https://github.com/akaion-ai/annona/releases/latest){ .an-btn .an-btn--primary }

</div>

Prefer a server? `docker compose up -d` brings up the kernel and a local model,
arm64 or amd64 — see
[deploying](https://github.com/akaion-ai/annona/blob/main/deploy/README.md).
Prefer a terminal? `pip install annona`, then
[turn the perimeter on](getting-started/perimeter.md) in five minutes.

## How it works

Four steps. Three never leave your machine, and the fourth happens only when the
policy says it may.

<div class="grid cards an-steps" markdown>

-   **1 · Classify**

    ---

    Every path, every payload, every tool result gets a class — from where it
    lives, what it contains, and what a prompt names. A run's class only ever
    goes **up**.

-   **2 · Place**

    ---

    From that class and the health of each substrate, the kernel picks where the
    step may run. Nothing permitted available → the step is **held**, not
    rerouted.

-   **3 · Execute**

    ---

    Tools run behind a default-deny gate: one the policy does not name does not
    run, deny beats allow, and symlinks are resolved to their targets.

-   **4 · Record**

    ---

    Every decision — including every refusal — lands in a hash-chained ledger you
    verify offline, with a command that contacts nobody.

</div>

```
$ annona why step_7f3a
step_7f3a  inference  HELD
  class        restricted  (working set touched /mnt/pratiche/2026/BG-114.pdf)
  rule         R-clienti  restricted → [local-gpu], on_unavailable: hold
  candidates   local-gpu (unhealthy: connection refused since 14:02:11)
  not chosen   frontier — max_class public < restricted
  outcome      held at 14:03:07
  ledger       #418  sha256:9c1f…a7  (chain verified)
```

That refusal **is** the product. A gateway in the same situation fails over to
the frontier API and returns a good answer.

## Why it exists

You have been told to pick one of three architectures: models **on-prem**
(private, capped by your hardware), **frontier APIs** (excellent, and your
material leaves), or **your own weights in your own cloud** (an honest compromise
that costs an MLOps team).

The industry argues about which column wins. That argument is the mistake.

!!! quote ""
    **The right column is a property of the request, not of the company.**

Summarising a public tender is not the same problem as reasoning over a client's
medical file, and the second does not become safe because procurement signed a
DPA. One organisation needs all three columns, chosen per step, ten thousand
times a day, by something that can prove afterwards what it chose.

## What you can do with it

<div class="grid cards" markdown>

-   **Keep privileged work inside**

    ---

    A client matter, a clinical record, a personnel file: read it, reason over
    it, and watch the frontier model that would have answered better simply not
    be called.

-   **Use the best model for everything else**

    ---

    Sovereignty is not a tax on all your traffic. A question with no client data
    goes to the best model you registered, at the price you chose.

-   **Answer with a frontier model anyway**

    ---

    A local PII model replaces the identifiers, the redacted question crosses,
    and the answer is re-identified here from a mapping that never left.

-   **Prove it afterwards**

    ---

    `annona verify`, `annona audit --held`, `annona why <step>` — an auditor's
    three questions, answered offline.

</div>

[Six use cases, each with the test that proves it](casi-duso.md){ .an-btn }
[Skills, with a jurisdiction](skills.md){ .an-btn }

## Honest about what it is not

- **Pseudonymous is not anonymous.** Redaction reduces exposure; the mapping
  exists, so it does not remove the need for a lawful basis.
- **No confidential computing on a GB10.** Encrypted memory and GPU attestation
  are real on HGX B200-class hardware, not on a DGX Spark. A privileged host
  administrator can read memory — on-prem that administrator is the customer,
  which is the point, but it belongs in the meeting rather than in an audit.
- **The ledger has no external anchor yet.** Tamper-evident against edits,
  deletions and reordering; a chain rebuilt wholesale by someone with write
  access is not detectable, and a test says so.
- **Small models still get tool arguments wrong.** Grammar-constrained decoding
  is the next piece, and the project's research claim.

Every guarantee here has a test with its name on it, and every gap has a row in a
table. That is the only way a vendor can ask to be believed about something a
customer cannot watch happening.

---

**Deploying this in an organisation?** [labs.akaion.com](https://labs.akaion.com) —
the kernel is open and always will be; what a company usually wants alongside it
is the policy written against their own folders, the hardware, and somebody who
answers when it breaks.

Built by [Akaion AI Lab](https://labs.akaion.com) on
[datapizza-ai](https://github.com/datapizza-labs/datapizza-ai) · interoperates
with [rizzo-pii](https://github.com/Rizzo-AI-Academy/rizzo-pii) · Apache-2.0
