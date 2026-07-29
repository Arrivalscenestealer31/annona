# Dogana

> *doh-GAH-nah* · Italian for **customs**

[![release](https://img.shields.io/github/v/release/Akaion-repos/akaion-app-runner?include_prereleases&label=release)](https://github.com/Akaion-repos/akaion-app-runner/releases)
[![license](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey)](#install)
[![ci](https://img.shields.io/badge/tests-313%20passing-brightgreen)](.github/workflows/ci.yml)

**Nothing crosses undeclared.**

The perimeter for AI agents. Dogana receives plans, executes them inside your
infrastructure, and produces a record of what left the building and what did not.

A customs post is the whole idea: everything crossing the border is declared,
checked against the rules, and either **cleared** or **held** — and a stamped
**manifest** survives the crossing.

It is a daemon you install where your data already lives. Agents act through it,
not around it: every tool call passes a policy check, every note stays on disk
as plain markdown, and nothing reaches a remote backend unless you say so.

> **Why this exists.** Agentic AI asks organisations to hand their internal
> systems to a remote model. For a law firm, a clinic, or an engineering
> practice, that trade is not available — the data is privileged by law. The
> usual answers are *powerful but not sovereign* (cloud copilots) or *sovereign
> but useless* (a local chatbot with no access to anything). The Runner is the
> third option: the model may be remote, the **execution and the data are not**.

> **Status: internal beta.** This repository is private during beta and bundles
> are unsigned. macOS will warn on first launch — right-click the app and pick
> **Open**. See [What it does not do yet](#what-it-does-not-do-yet) for an honest
> account of the gaps.

## The trust boundary

The Runner is open source on purpose, and the boundary is deliberate. It is the
component that touches your data, so it must be the component you can read.

|  | **Runner** (this repo, Apache-2.0) | **Agents Studio** (hosted, proprietary) |
|---|---|---|
| Decides *what* to do | no | yes — plans, versions, fleet |
| Decides *whether it may* | **yes, and it is the only one that does** | no |
| Sees your data | yes, and does not let it leave | never in the clear |
| Runs where | your machine, your server, your appliance | EU cloud |

You can run the Runner with no account at all, point it at your own backend, or
fork it and replace the cloud side entirely — three HTTP endpoints, documented
in [Self-hosting the cloud side](#self-hosting-the-cloud-side).

## Where it runs

Three topologies, **one binary, one release**. They differ in configuration —
which backends are registered and what the policy permits — never in code. A fork
per deployment is how sovereignty claims rot, so there isn't one.

| | **Detached** | **Attached** | **Appliance** |
|---|---|---|---|
| Hardware | laptop, Mac mini in a cupboard | any | DGX-class, or EU colocation |
| Control plane | none — local plans and CLI | Agents Studio, outbound-only | Agents Studio |
| Inference | local runtime only | local + remote, routed by policy | local (vLLM), remote by exception |
| Users | one | one | many, per-user policy |
| Network | may be fully air-gapped | outbound 443 only | outbound 443 only |

```yaml
# ~/.akaion/config.yaml — the axis that selects a topology
profile: detached        # detached | attached | appliance
```

Detached means detached: no account, no remote host, no outbound connection at
all. It is the configuration we expect a fork to start from.

## How data moves

Three rules, enforced by the daemon's shape rather than by a promise:

- **Outbound-only.** The Runner opens no listening port to the internet. It
  polls. There is nothing to expose, nothing to firewall, no inbound rule to
  request from a client's IT department.
- **Nothing leaves by default.** Cloud sync is opt-in (`cloud.enabled: false` is
  the shipped default). Until you flip it, the Runner never contacts a remote
  host except to authenticate if you ask it to.
- **Push, never pull.** Notes go local → remote, per note, on your command.
  Cloud content is never written into your vault. Deleting `~/akaion-brain/`
  deletes everything the Runner knows.

The Runner contacts a remote backend in exactly three situations: you log in,
you push pending notes, or a plan runs against a cloud model provider. Each is
an explicit action. There is no telemetry and no background upload.

## Install

### Native app (`.dmg` / `.AppImage` / `.exe`) — recommended

Download the latest build for your platform from
[Akaion-repos/akaion-app-runner/releases](https://github.com/Akaion-repos/akaion-app-runner/releases).

- **macOS Apple Silicon**: `Akaion Runner_<ver>_aarch64.dmg`
- **macOS Intel**: `Akaion Runner_<ver>_x64.dmg`
- **Windows**: `Akaion Runner_<ver>_x64-setup.exe` (or `.msi`)
- **Linux**: `Akaion Runner_<ver>_amd64.AppImage` (or `.deb`)

On macOS, drag to `/Applications` and launch from Spotlight. The first launch
needs a right-click → **Open** because the bundle is unsigned during beta.

With the `gh` CLI:

```bash
# macOS arm64 (M-series)
gh release download v0.1.0 -R Akaion-repos/akaion-app-runner --pattern "*aarch64.dmg"
open "Akaion Runner_0.1.0_aarch64.dmg"

# Linux
gh release download v0.1.0 -R Akaion-repos/akaion-app-runner --pattern "*.AppImage"
chmod +x Akaion\ Runner_*.AppImage && ./Akaion\ Runner_*.AppImage
```

### From source

```bash
git clone git@github.com:Akaion-repos/akaion-app-runner.git
cd akaion-app-runner
make setup          # venv + dependencies
make demo           # see it run — no credentials, no network
make run            # daemon + local UI on 127.0.0.1:7070
```

Open `http://127.0.0.1:7070`. No account required.

`make demo` is the fastest way to understand this repository. It runs a **real
agentic loop** — real tool execution against real files, real policy checks —
against a scripted backend, so it needs no API key and opens no socket. It shows
one task the policy permits and one it refuses:

```
1 · a task the policy permits
  1. ok      explorer         {'operation': 'map', 'path': '…/documents'}
     → {'success': True, …}
  2. ok      document_reader  {'path': '…/reports/q1_report.txt'}
     → {'success': True, …}

  answer     Q1 2026: 142 pratiche aperte, 98 chiuse, 412.000 EUR…

2 · a task the policy refuses
  1. denied  filesystem       {'operation': 'read', 'path': '~/.ssh/id_rsa'}
     → {'error': 'Permission denied for tool: filesystem'}
```

The same run is a CI gate on every push: `python -m runner.demo --check`.

## What it does

### Local memory

Every note lives under `~/akaion-brain/` as a markdown file, indexed in SQLite
at `~/akaion-brain/.akaion/index.db`. The vault is greppable, diffable and
Git-friendly: walk away from the Runner and your prose is still plain markdown
that any tool can read.

One caveat, stated plainly: **the markdown holds the body only.** Titles, tags
and sync state live in the SQLite index, and files are named by uuid rather than
by title. Today you keep the text and lose the structure. Writing YAML
frontmatter would fix it, and is a storage migration rather than a refactor — see
the gap table below.

```bash
./start.sh
# → http://127.0.0.1:7070 → "Open my vault" (no login)
```

### Local execution

Plans arrive as tasks and execute on the machine through a tool registry:
filesystem, shell, browser, a document reader (PDF, DOCX, XLSX, CSV, source
files), and a filesystem explorer. Every call is checked against the policy in
`~/.akaion/config.yaml` before it runs, and every executed task can be captured
back into the vault as a note (`runner.capture_to_brain`).

Reasoning can come from a cloud provider (Akaion, Anthropic, OpenAI, Google) or
from a local model over Ollama. See
[What it does not do yet](#what-it-does-not-do-yet) for the current limits of
local reasoning — this is the gap we are closing next.

### Optional cloud sync

With an Akaion account, or your own compatible backend:

1. Sidebar → **Sync with Akaion Cloud** → sign in.
2. Mark a note `pending` in the Brain view.
3. Sidebar → **Sync** → **Push pending**.

## What it does not do yet

Published deliberately, because a perimeter you cannot verify is a slogan. These
are the gaps between the claim above and the code in this repository today:

| Gap | Today | Tracked in |
|---|---|---|
| **Policy is default-allow** | `PermissionManager` permits any tool it does not recognise, and permits everything in a category whose allow-list is empty. It is an advisory filter, not an enforcing kernel. | [Research § Enforcement](docs/research/index.md) |
| **No egress control** | Policy covers what a tool may *touch*. Nothing yet classifies or gates what leaves the perimeter toward a model provider. | [Research § PCR](docs/research/index.md) |
| **No measured leak rate** | "Your data does not leave" is currently an architectural argument, not a number. | [Research § Leak canary](docs/research/index.md) |
| **Audit trail is a log file** | Tool calls are logged, but the log is not tamper-evident and cannot be independently verified. | [Research § Trace-as-proof](docs/research/index.md) |
| **Local reasoning has no tool use** | With `ai.provider: local`, the agentic loop falls back to plain chat completion. Fully local mode can talk; it cannot yet act. | [Research § Local agentic loop](docs/research/index.md) |
| **Vault metadata is not portable** | Markdown files hold the note body. Titles, tags and sync state exist only in the SQLite index, and files are named by uuid. Asserted in `tests/test_e2e_topologies.py` so it cannot change silently. | frontmatter migration |

Closing these is the research programme, not a backlog of chores. Each one has a
metric attached — see [`docs/research/index.md`](docs/research/index.md).

## CLI

```bash
akaion init                    # one-time setup (creates ~/.akaion/config.yaml)
akaion run                     # start the daemon (long-lived UI server)
akaion run --once --task ".."   # execute a single ad-hoc task
akaion login / logout          # Akaion Cloud credentials (optional)
akaion cloud enable / disable   # toggle cloud push capability
akaion status                  # config, vault stats, cloud connection
akaion note add "title"        # create a note
akaion note list               # list notes
akaion sync push               # push every note marked pending
```

## Configuration

Two layers: a YAML file under `~/.akaion/` and environment variables.

### `~/.akaion/config.yaml`

```yaml
cloud:
  enabled: false            # default: pure local. `akaion cloud enable` flips this.
  api_url: https://api.prod.akaion.com
  polling_interval: 5
  timeout: 30
ai:
  provider: akaion          # akaion | anthropic | openai | google | local
  local:
    endpoint: http://localhost:11434   # Ollama
runner:
  capture_to_brain: true    # save every executed task as a local note
permissions:
  filesystem:
    allowed_paths: [~/Documents, ~/Downloads]
    denied_paths:  [~/.ssh]
  shell:
    enabled: true
    allowed_commands: [ls, cat, grep, find, git]
logging:
  level: INFO
  file: logs/runner.log
```

An empty allow-list currently means *allow all* for that category — see
[What it does not do yet](#what-it-does-not-do-yet). Write your allow-lists
explicitly until that inverts.

### Environment variables

See [`.env.example`](.env.example) for the full list. The Runner reads them from
`~/.akaion/.env` or the shell. `start.sh` loads `.env.prod` / `.env.dev`
profiles via `RUNNER_ENV=prod|dev`.

| Variable | Purpose | Default |
|---|---|---|
| `AKAION_API_BASE` | Cloud backend host | `https://api.prod.akaion.com` |
| `AKAION_HOME` | Config + auth + vault parent dir | `~/.akaion` |
| `AKAION_BRAIN_DIR` | Vault directory | `~/akaion-brain` |
| `AKAION_LOG_LEVEL` | Loguru log level | `INFO` |

## Architecture

```
~/akaion-brain/                          ← vault (markdown + SQLite)
├── notes/
│   ├── 2026-05-19-meeting.md
│   └── …
└── .akaion/index.db                     ← search + sync state

~/.akaion/                               ← runner config
├── config.yaml
├── auth.json                            ← encrypted Firebase ID token
└── .key                                 ← Fernet key for auth.json

akaion-app-runner/
├── runner/
│   ├── kernel/                  L0  value types · ports · block translation
│   ├── capability/              L1  backends/ (echo, anthropic, akaion) · tooling
│   ├── agent/                   L3  the agentic loop · system prompt
│   ├── demo.py                  L4  offline end-to-end run
│   ├── ai_client.py             L4  composition root: constructs and wires
│   ├── cli.py · local_api.py    L4  CLI · /api/* on 127.0.0.1:7070
│   ├── tools/                       filesystem, shell, browser, documents, explorer
│   ├── permissions/manager.py       policy checks on every tool call
│   ├── brain/ · sync/               markdown vault + SQLite · one-way push
│   └── main.py · executor.py        daemon · task dispatch
└── ui/                              React + Tauri shell (.dmg/.AppImage/.exe)
```

The layer numbers are not decoration — they are enforced. `lint-imports` checks
five contracts on every build, two of which assert that **neither the kernel nor
the agent loop can import a provider SDK**. "Provider-agnostic" is a checked fact
here, not an intention:

```
$ make contracts
L0 kernel does not depend on outer layers                    KEPT
L3 agent depends only inward on L0                           KEPT
L3 agent and L1 capability do not know about each other      KEPT
L0 kernel imports no provider SDK                            KEPT
L3 agent loop imports no provider SDK                        KEPT
```

[`docs/design/architecture.md`](docs/design/architecture.md) describes the code as it is today.
[`docs/design/sovereign-runtime.md`](docs/design/sovereign-runtime.md) is the
design we are moving to — layers, the perimeter as a total mediator, the threat
model, and what is deliberately not defended.
[`docs/research/index.md`](docs/research/index.md) states what we are trying to prove.

### Built on datapizza-ai

The execution core builds on
[`datapizza-ai`](https://github.com/datapizza-labs/datapizza-ai) (MIT, Datapizza
Labs) rather than on a fourth in-house agent framework. It supplies the canonical
message vocabulary, provider adapters, tool schemas and the loop skeleton; local
runtimes reach it through the `openai-like` client, which any OpenAI-compatible
endpoint satisfies — Ollama, llama.cpp, vLLM.

What this repository adds is the part that does not exist elsewhere: the
perimeter (default-deny policy, classification, egress gate, fail-closed), local
tool calling via constrained decoding, and a tamper-evident trace. The
grammar-constrained clients are generally useful and carry no competitive value —
we intend to upstream them.

## Self-hosting the cloud side

The Runner talks to three HTTP endpoints. Implement them and it will point at
your infrastructure instead of ours:

| Endpoint | Used for | Required |
|---|---|---|
| `GET /api/service1/api/v1/users/me` | Verify token | yes |
| `POST /api/service3/api/v1/cloud/thoughts` | Receive pushed notes | yes |
| `POST /api/service4/api/v1/runner/agent/turn` | Cloud LLM inference | no |

Set `AKAION_API_BASE`, use your own Firebase project (`FIREBASE_API_KEY`), done.
Or set `ai.provider: local` and skip the third entirely.

## Research

The Runner is the reference implementation for work at **Akaion AI Lab** on
*measurable sovereignty*: not "your data is safe" but a measured leak rate, a
cost/privacy frontier, and a command you run yourself to check the claim.

Open questions, metrics, and results live in
[`docs/research/index.md`](docs/research/index.md). Negative results are published there
too.

## Development

```bash
make setup            # venv + runtime + dev dependencies
make check            # lint · types · contracts · tests — exactly what CI runs
make test-cov         # coverage report
make demo             # offline end-to-end run
make docs-serve       # documentation at 127.0.0.1:8000
make                  # list every target
```

Individually:

```bash
make lint             # ruff
make typecheck        # mypy — strict on runner/{kernel,capability,agent}
make contracts        # lint-imports — the five architectural contracts
./start.sh --dev            # verbose logging
./start.sh --tauri-dev      # desktop shell against the live UI

./scripts/build-sidecar.sh          # PyInstaller → ui/src-tauri/binaries/
cd ui && npm run tauri build        # → .dmg / .AppImage / .exe
```

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Apache 2.0
([`LICENSE`](LICENSE), [`NOTICE`](NOTICE)). Security reports:
[`SECURITY.md`](SECURITY.md).

Two things worth knowing up front:

- **Do not mock a vendor SDK in tests.** Use the `echo` backend and drive the loop
  through its ports — see `tests/test_agent_loop_unified.py`.
- **If you change anything on the trust boundary** — permissions, sync, egress,
  the audit trail — say in the PR description what a reviewer should check to
  convince themselves the boundary still holds. Not "I tested it": what to look
  at.

The Firebase Web API key in `auth.py` and `ui/src/lib/firebase.ts` is the
project's documented public default; Firebase Web SDK keys are designed to be
client-visible.

## Releases

Tagged releases (`v*`) trigger
[`.github/workflows/release.yml`](.github/workflows/release.yml): a 4-target
matrix (macOS arm64, macOS x64, Linux x64, Windows x64) publishing a draft
GitHub Release with all bundles attached. Promote draft → published manually
after smoke testing.

## License

Apache 2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

Copyright 2026 Akaion.
