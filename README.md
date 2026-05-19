# Akaion Runner

[![release](https://img.shields.io/github/v/release/Akaion-repos/akaion-app-runner?include_prereleases&label=release)](https://github.com/Akaion-repos/akaion-app-runner/releases)
[![license](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey)](#install)

Local-first second brain. A markdown vault, a SQLite index, a small FastAPI
server, and a desktop UI you open in your browser at `http://127.0.0.1:7070`.
Works offline. Optionally pushes notes to an Akaion-compatible cloud — never
pulls. Your data stays where you put it.

> Think of it as **Obsidian + an optional "publish to cloud" button**, packaged
> as a tiny daemon you can install with one command.

> **Internal beta.** This repository is private and unsigned bundles are
> distributed via GitHub Releases inside the Akaion organization. macOS will
> warn on first launch — right-click the app and pick **Open** to bypass
> Gatekeeper.

## Why

Most "second brain" tools force a choice: full cloud (your data is theirs) or
fully local (you lose collaboration and search across devices). Akaion Runner
inverts that: notes live on disk as plain markdown, the daemon serves a UI, and
you decide which notes (if any) get pushed to a remote backend you trust.

- ✅ Plain `.md` files + SQLite index — your vault is greppable and Git-friendly
- ✅ One-way sync: local → remote, on demand, per-note
- ✅ Single binary distribution via Tauri (`.dmg`, `.AppImage`, `.exe`)
- ✅ Apache 2.0 — fork it, self-host the cloud side, run your own backend
- ❌ No telemetry, no analytics, no background uploads

## Install

### Native app (`.dmg` / `.AppImage` / `.exe`) — recommended

Download the latest release for your platform from
[Akaion-repos/akaion-app-runner/releases](https://github.com/Akaion-repos/akaion-app-runner/releases).

- **macOS Apple Silicon**: `Akaion Runner_<ver>_aarch64.dmg`
- **macOS Intel**: `Akaion Runner_<ver>_x64.dmg`
- **Windows**: `Akaion Runner_<ver>_x64-setup.exe` (or `.msi`)
- **Linux**: `Akaion Runner_<ver>_amd64.AppImage` (or `.deb`)

On macOS, drag to `/Applications`. Launch from Spotlight. The first launch
needs a right-click → **Open** because the bundle is unsigned during beta.

With `gh` CLI from the terminal:

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
./install.sh        # creates venv, installs deps, builds UI
./start.sh          # boots the daemon on :7070
```

Open `http://127.0.0.1:7070` in your browser. That's it — you're in.

### One-line install (planned)

```bash
# Not yet hosted — TODO once install.akaion.com is wired up.
# curl -fsSL https://install.akaion.com/runner.sh | bash
```

## Usage

### Local-only (no account needed)

```bash
./start.sh
# Open http://127.0.0.1:7070
# Click "Apri il mio Brain" — no login required
```

Every note you write lives under `~/akaion-brain/` as a markdown file. The
daemon indexes them in `~/akaion-brain/.akaion/index.db` (SQLite). Search is
local and instant. Delete the vault directory and the runner is forgotten.

### Optional: push to the cloud

If you have an Akaion account (or a self-hosted Akaion-compatible backend),
you can push selected notes to it:

1. Sidebar → **Sincronizza con Akaion Cloud** → log in with Google.
2. In the Brain view, mark a note as `pending` (tag with sync intent).
3. Sidebar → **Sync** → **Push pending**. The note ships to the cloud as a
   thought; the cloud assigns it to a semantic cluster and returns metadata.

The runner **never pulls thoughts from the cloud back to your vault**. Cloud
notes stay on the cloud; local notes stay on your Mac. This is by design.

## CLI

```bash
akaion init                  # one-time setup (creates ~/.akaion/config.yaml)
akaion run                   # start the daemon (long-lived UI server)
akaion run --once --task ".."  # execute a single ad-hoc task
akaion login                 # sign in to Akaion Cloud (optional)
akaion logout                # forget cloud credentials
akaion cloud enable          # turn on cloud push capability
akaion cloud disable         # back to pure local mode
akaion status                # show config, vault stats, cloud connection
akaion note add "title"      # CLI shortcut to create a note
akaion note list             # list notes from the terminal
akaion sync push             # push every note marked pending
```

## Configuration

Two layers: a YAML file under `~/.akaion/` and environment variables.

### `~/.akaion/config.yaml`

```yaml
cloud:
  enabled: false            # default: pure local. `akaion cloud enable` flips this.
  api_url: https://api.akaion.com
  polling_interval: 5
  timeout: 30
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

### Environment variables

See [`.env.example`](.env.example) for the full list. The runner reads them
from `~/.akaion/.env` or any shell-exported variable. `start.sh` can also
load `.env.prod` or `.env.dev` profiles when invoked with `RUNNER_ENV=prod|dev`.

The variables that matter most:

| Variable | Purpose | Default |
|---|---|---|
| `AKAION_API_BASE` | Cloud backend host | `https://api.akaion.com` |
| `AKAION_HOME` | Config + auth + vault parent dir | `~/.akaion` |
| `AKAION_BRAIN_DIR` | Vault directory | `~/akaion-brain` |
| `AKAION_LOG_LEVEL` | Loguru log level | `INFO` |

## Architecture

```
~/akaion-brain/                          ← vault (markdown + SQLite)
├── notes/
│   ├── 2026-05-19-meeting.md
│   └── …
└── .akaion/
    └── index.db                         ← SQLite index for search/sync state

~/.akaion/                               ← runner config
├── config.yaml                          ← YAML config (see above)
├── auth.json                            ← encrypted Firebase ID token (if logged in)
└── .key                                 ← Fernet key for auth.json

akaion-runner/
├── runner/                              ← Python daemon
│   ├── main.py                          ← idle-loop daemon + FastAPI server
│   ├── auth.py                          ← Firebase auth + token cache
│   ├── brain/manager.py                 ← markdown vault + SQLite index
│   ├── sync/engine.py                   ← one-way push to COT backend
│   ├── local_api.py                     ← /api/* endpoints on :7070
│   ├── service_urls.py                  ← env-driven backend URL resolver
│   └── cloud_client.py                  ← HTTP clients (auth verify, AI calls)
└── ui/                                  ← React + Tauri shell
    ├── src/                             ← TypeScript UI
    └── src-tauri/                       ← Rust shell for the native .dmg
```

The runner has **zero background traffic** to the cloud. It will only contact
a remote backend when:

- you log in (auth flow);
- you click "Push" in the Sync view;
- you manually call `akaion sync push` from the CLI.

## Self-hosting the cloud side

Akaion Runner talks to three HTTP endpoints. If you want to point it at your
own backend instead of `api.akaion.com`, implement these three:

| Endpoint | Used for | Required |
|---|---|---|
| `GET /api/service1/api/v1/users/me` | Verify Firebase token | yes |
| `POST /api/service3/api/v1/cloud/thoughts` | Receive pushed notes | yes |
| `POST /api/service4/api/v1/runner/agent/turn` | Optional cloud LLM inference | no |

Set `AKAION_API_BASE` to your host, log in with a Firebase project of your
choice (`FIREBASE_API_KEY`), done.

## Development

```bash
# Backend (Python)
./install.sh
./start.sh --dev                    # verbose logging

# UI hot-reload (Tauri + Vite)
./start.sh --tauri-dev              # opens the desktop shell against the live UI

# Tests
pytest                              # unit + integration

# Build native installers
./scripts/build-sidecar.sh          # PyInstaller → ui/src-tauri/binaries/
cd ui && npm run tauri build        # → .dmg / .AppImage / .exe
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the deeper dive.

## Contributing

Internal beta — PRs are reviewed inside the Akaion org. The project is
licensed under Apache 2.0 ([`LICENSE`](LICENSE), [`NOTICE`](NOTICE)).

Before opening a PR:

1. Run `pytest` (runner-side suite, no cloud needed)
2. If you touch the UI: `cd ui && npm run build` must succeed
3. Keep secrets out — there is no API key worth committing. The Firebase Web
   API key in `auth.py` and `ui/src/lib/firebase.ts` is the project's documented
   public default; Firebase Web SDK keys are designed to be client-visible

## Releases

Tagged releases (`v*`) automatically trigger
[`.github/workflows/release.yml`](.github/workflows/release.yml), which runs a
4-target matrix (macOS arm64, macOS x64, Linux x64, Windows x64) and publishes
a draft GitHub Release with all bundles attached. Promote draft → published
manually after smoke testing.

## License

Apache 2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

Copyright 2026 Akaion.
