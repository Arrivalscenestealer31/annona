# Akaion Runner

Local-first second brain. A markdown vault, a SQLite index, a small FastAPI
server, and a desktop UI you open in your browser at `http://127.0.0.1:7070`.
Works offline. Optionally pushes notes to an Akaion-compatible cloud — never
pulls. Your data stays where you put it.

> Think of it as **Obsidian + an optional "publish to cloud" button**, packaged
> as a tiny daemon you can install with one command.

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

### macOS / Linux (one-liner)

```bash
curl -fsSL https://install.akaion.com/runner.sh | bash
```

### From source

```bash
git clone https://github.com/akaion/akaion-runner.git
cd akaion-runner
./install.sh        # creates venv, installs deps, builds UI
./start.sh          # boots the daemon on :7070
```

Open `http://127.0.0.1:7070` in your browser. That's it — you're in.

### Native app (`.dmg` / `.AppImage` / `.exe`)

Download the latest release from
[github.com/akaion/akaion-runner/releases](https://github.com/akaion/akaion-runner/releases).
Drag to `/Applications`, launch. The daemon runs in the menubar.

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

Issues and PRs welcome. The project is Apache 2.0 licensed — see
[`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

Before opening a PR:

1. Run `pytest` (the runner-side suite, no cloud needed)
2. If you touch the UI, run `cd ui && npm run build` to make sure it compiles
3. Keep secrets out — there is no API key worth committing. The Firebase web
   key in `auth.py` is the documented public default

## License

Apache 2.0. See [`LICENSE`](LICENSE).

Copyright 2026 Akaion.
