# Changelog

Notable changes to this project. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project follows
[semantic versioning](https://semver.org/) from 1.0 onward.

## [Unreleased]

### Named: Dogana

The project has a name — *Dogana*, Italian for customs — and the vocabulary that
comes with it: **declaration**, **clearance**, **manifest**, **held**. See
[ADR 0004](docs/adr/0004-name-the-project-dogana.md).

`dogana` is installed as an equal alias; `akaion` still works. The Python package
stays `runner`.

### Fixed — two divergent CLIs

`runner/cli.py` and the root `cli.py` were **two separate CLIs**, and they had
drifted. The one `pip` installed was the stale copy: it had no `note`, `sync` or
`cloud` commands — which the README documents — and six shared commands differed
in options and in how they resolved service URLs. A user got a different program
depending on whether they installed the wheel or the `.dmg`.

There is now one CLI in `runner/cli.py` (all 12 commands, `dashboard` included)
and a 21-line shim at the root for PyInstaller.

### Changed — English throughout

399 lines of Italian across 36 files: CLI help and output, docstrings, comments,
the desktop UI, and the quickstart. The project ships in English.

`docs/getting-started/quickstart.md` was three documents in one; the release
engineering and auto-updater halves moved to `docs/reference/releasing.md`.

### Added — end-to-end coverage of both topologies

`tests/test_e2e_topologies.py` (15 tests) covers what no test covered before:

- **Detached** — a full agentic run with no credentials and no network; sync
  without credentials as a silent no-op rather than a `Bearer None` request.
- **Attached** — a **live HTTP server** implementing the documented
  three-endpoint contract. Auth verification, a note pushed with the exact
  documented payload, an agentic turn planned remotely and executed locally, a
  policy denial reported upstream without leaking the file, and an unreachable
  control plane degrading instead of crashing.

The attached tests use a real server rather than a mocked client on purpose: the
README tells people they can point the runner at their own backend, and this is
what proves it.

### Fixed — the shipped cloud host was wrong

`service_urls.DEFAULT_API_BASE`, `.env.example` and `.env.prod` all pointed at
`https://api.akaion.com`, which does not serve the API — the TLS handshake fails.
The production gateway is **`https://api.prod.akaion.com`**, where all three
documented services answer: `service1` and `service3` return 200 on `/health`,
`/api/v1/users/me` returns a structured 401, and both write endpoints return 405
on GET, proving the routes exist rather than a catch-all answering.

A fresh clone could not complete `akaion login`. Every default now points at the
real gateway.

`tests/test_live_cloud.py` pins it: seven checks against the real gateway,
opt-in via `AKAION_LIVE=1` so CI stays hermetic. Set `AKAION_LIVE_TOKEN` to
exercise the authenticated path as well.

```bash
AKAION_LIVE=1 env/bin/python -m pytest tests/test_live_cloud.py -v
```

### Known issues found while testing

- **Vault metadata is not portable.** Markdown files hold the note body only;
  titles, tags and sync state live in the SQLite index, and files are named by
  uuid. "Walk away and keep your data" was true of the prose and false of the
  structure. The README now says so, and a test asserts it so it cannot change
  unnoticed.


### Phase 0 — one loop, behind ports

The agentic loop existed three times: once per provider, of which only two
supported tool use. That meant three places where content could leave the
perimeter, so no egress control could ever be total. This release makes it one.

No observable behaviour changed. The existing suite — 205 tests, 34 of them
covering both provider loops — passes unchanged.

#### Added

- `runner/kernel` (L0) — immutable value types, the three ports the loop depends
  on (`InferenceBackend`, `ToolExecutor`, `PolicyGate`), an error taxonomy, and
  translation to and from datapizza blocks.
- `runner/capability` (L1) — inference adapters for `anthropic`, `akaion` and the
  new offline `echo` backend, a shared Anthropic-style wire encoder, and adapters
  putting the existing tool registry and permission manager behind the ports.
- `runner/agent` (L3) — the single agentic loop, and the system prompt as its own
  testable unit.
- `runner/demo.py` — a real agentic run with no credentials and no network.
  `make demo` narrates it; `python -m runner.demo --check` verifies it and runs in
  CI on four platform and version combinations.
- `ai.provider: echo` — a scripted, deterministic, offline backend. Useful beyond
  testing: it drives an exact sequence of tool calls without spending tokens.
- 93 tests across the kernel, the adapters, the loop, and an offline end-to-end
  suite. Total: 298 passing, 6 skipped.
- Architectural contracts in `.importlinter`, enforced in CI. Five of them, two of
  which prove that neither the kernel nor the loop can import a provider SDK.
- `pyproject.toml` (PEP 621), `Makefile`, `.pre-commit-config.yaml`, a `ci`
  workflow, ruff, mypy, and a coverage configuration.
- Documentation: an mkdocs site, three ADRs, a rewritten architecture page, a
  local UI design spec, a configuration reference, a backend authoring guide, plus
  `CONTRIBUTING.md`, `SECURITY.md` and this file.

#### Changed

- `AIClient` is now the composition root. It constructs provider clients and wires
  ports to adapters; it no longer contains control flow. `reason_and_execute`
  returns the same dictionary as before.
- **Text aggregation is uniform.** The Akaion path kept only the last text block
  of a turn while the Anthropic path joined them all. Both now join. A model that
  commented before calling a tool previously had that commentary discarded on the
  Akaion path.
- **`max_iterations=0` returns instead of raising.** It previously raised
  `UnboundLocalError` from an unbound loop variable.
- **Unserialisable tool results degrade instead of raising.** Encoding used
  `json.dumps` with no fallback, so a `Path` in a tool result ended the run.
- Documentation restructured under `docs/` for mkdocs. `docs/ARCHITECTURE.md` was
  rewritten in English: it described a control-plane polling loop and three
  agentic loops, none of which existed.

#### Fixed

- **pytest configuration was silently ignored.** `pytest.ini` used the `setup.cfg`
  spelling `[tool:pytest]`, so pytest never applied it — `addopts`, coverage and
  markers had no effect, and `pytest-cov` was not even installed. Configuration
  now lives in `pyproject.toml`.
- **`asyncio==3.4.3` removed from `requirements.txt`.** `asyncio` is in the
  standard library; the PyPI package of that name is a 2015 backport that shadows
  it. Also removed duplicate pins for `rich`, `click` and `typer`.
- **Manual scripts no longer run as tests.** `test_e2e.py` and `test_runner_ai.py`
  sat at the repository root, where pytest collected them by name — a cloud probe
  requiring a Firebase token was part of the suite. They moved to
  `scripts/manual/`.
- 43 unused imports removed and 38 import blocks sorted across the codebase.

#### Known gaps

Unchanged by this release and documented with metrics in
[docs/research](docs/research/index.md):

- policy is allow-by-default;
- nothing classifies or gates egress;
- the audit trail is a log file, not a verifiable artefact;
- `openai`, `google` and `local` still reach a model without being able to call
  tools. Phase 2 closes the last one with real local inference.

[Unreleased]: https://github.com/Akaion-repos/akaion-app-runner/compare/v0.1.0...HEAD
