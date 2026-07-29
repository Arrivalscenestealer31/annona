# 0003 — Ship an offline scripted backend in the product

- **Status:** Accepted
- **Date:** 2026-07-28
- **Deciders:** Akaion AI Lab

## Context

Two problems with one shape.

**Testing.** Every test of the loop went through a mocked vendor SDK — building
`MagicMock` objects with `.type`, `.text` and `.stop_reason` attributes to imitate
Anthropic's response model. Those tests assert against a mock's shape as much as
against our behaviour, and they cannot be written at all for a provider nobody has
credentials for.

**Evaluation.** Someone assessing a sovereignty product needs to see it run before
they will give it an API key, and "clone it, get a key, configure a provider,
then see what it does" loses most readers. For a project whose central claim is
*verify it yourself*, a first run that requires trusting a vendor first is a
contradiction.

## Decision

Ship `EchoBackend` — an `InferenceBackend` that plays back a fixed script of
completions — as part of the product, selectable with `ai.provider: echo`, and
build `python -m runner.demo` on it.

The demo runs a real agentic loop: real tool execution against real files, real
permission checks, a real transcript. Only the reasoning is scripted.

`make demo` narrates it. `python -m runner.demo --check` verifies it and exits
non-zero on failure, and runs in CI on every push across four platform and
version combinations.

Scripts can also come from configuration:

```yaml
ai:
  provider: echo
  echo:
    script:
      - text: "Let me look at that directory."
        tools:
          - name: explorer
            arguments: { operation: map, path: "~/Documents" }
      - text: "Done — the tree is above."
```

Malformed scripts raise `ConfigurationError` rather than being partially applied.

## Alternatives considered

**Keep it in `tests/` as a fixture.** Rejected: then it cannot back a demo, and
the onboarding problem stays unsolved. It is also genuinely useful to an operator
debugging a policy — you can drive an exact sequence of tool calls without
spending tokens or hoping a model cooperates.

**Record and replay real provider responses (VCR-style).** Better fidelity, and
worth doing later for regression fixtures. Rejected for now: cassettes have to be
recorded with real credentials, they carry whatever the model said that day, and
scrubbing them is its own project.

**Have it improvise — parse the transcript and pick a plausible tool.** Rejected
outright. A test double that improvises hides bugs, and a demo that improvises is
a lie about what the system does. When the script runs out it says so and stops.

## Consequences

**Good.**

- Loop behaviour — iteration budgets, parallel calls, policy denials, partial
  results after a backend drops out — is tested without a single SDK mock.
- A fresh checkout demonstrates itself in ten seconds with no credentials and no
  network.
- CI exercises the layers composed, which no unit test does.
- It is the only Phase 0 backend with `Capabilities.is_local = True`, which makes
  the meaning of that field concrete before Phase 1 reads it.

**Bad, and accepted.**

- A backend in the product that is not a model. Mitigated by naming: the module
  docstring, the config value and the demo output all say the reasoning is
  scripted. The demo prints it in its closing line.
- Someone could point a production config at `echo` and get a runner that does
  nothing intelligent. It fails loudly and visibly rather than silently, and
  Phase 2 gives local inference a real backend to point at instead.
