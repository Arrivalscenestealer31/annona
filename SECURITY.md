# Security policy

## Reporting a vulnerability

Email **security@akaion.com**. Do not open a public issue.

Include what you can: affected version or commit, a reproduction, and what an
attacker gains. We aim to acknowledge within three working days and to agree a
disclosure timeline with you.

## What this project defends against

The Runner exists to keep a *misbehaving model* from doing damage with the access
it has been given. Reports in scope:

- a tool call that escapes its configured filesystem, shell or network policy;
- prompt injection in a document that causes exfiltration or destruction;
- a plan from a control plane that raises its own privileges;
- data reaching a remote host that the configuration did not authorise;
- credentials readable from tool code, or written somewhere they should not be.

## What it does not defend against

Listed so nobody spends time on a claim we do not make:

- **root on the machine, or a malicious operator.** The policy, the keys and the
  logs live on the same box.
- **a model extracting data through an allow-listed tool's legitimate output.**
  If a tool may reach the network and the model may call it, that is a channel the
  configuration opened.
- **side channels** — timing, token counts — against a remote backend.

## Two things worth knowing before you file

**A `shell` tool with unrestricted commands voids any egress claim.** A model that
can run `curl` needs no help from the inference path; the same goes for a browser
tool with arbitrary URLs. This is documented, not accidental —
[Sovereign runtime](docs/design/sovereign-runtime.md) §4.3. A report that a
permissive shell configuration allows exfiltration describes the configuration
working as specified. A report that an allow-list is *bypassed* is a real finding.

**Remote backends send the whole transcript.** With `ai.provider: akaion` or
`anthropic`, tool results — the contents of every file the agent read — are sent
on the following turn. Local tool execution is not local data handling. This is
stated in the README, the architecture page and the configuration reference. It is
a known property, and closing it is Phase 1.

## Known gaps

Published deliberately, with metrics, in
[docs/research](docs/research/index.md):

| Gap | Status |
|---|---|
| Policy is allow-by-default | Open — Phase 1 inverts it |
| No egress classification or gate | Open — Phase 1 |
| No measured leak rate | Open — leak canary harness |
| Audit trail not tamper-evident | Open — Phase 3 |

If you find something in that list, we know. If you find a way to make one of them
worse than described, we want to hear it.

## Supported versions

Pre-1.0: the latest release only.
