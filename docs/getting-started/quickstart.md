# Quickstart

From a fresh clone to a working agentic run, offline, in about a minute.

## 1. Set up

```bash
git clone git@github.com:Akaion-repos/akaion-app-runner.git
cd akaion-app-runner
make setup
```

Creates a virtual environment, installs runtime and development dependencies, and
installs the `akaion` command. Python 3.10+ is the only prerequisite.

## 2. See it run

```bash
make demo
```

This is a **real agentic loop** — real tool execution against real files, real
policy checks — driven by a scripted backend, so it needs no API key and opens no
socket. It shows one task the policy permits and one it refuses:

```
1 · a task the policy permits
  1. ok      explorer         {'operation': 'map', 'path': '…/documents'}
  2. ok      document_reader  {'path': '…/reports/q1_report.txt'}
  answer     Q1 2026: 142 open matters, 98 closed, EUR 412,000 …

2 · a task the policy refuses
  1. denied  filesystem       {'operation': 'read', 'path': '~/.ssh/id_rsa'}
     → {'error': 'Permission denied for tool: filesystem'}
```

Nothing left the process. That is the product in one screen.

## 3. Start the runner

```bash
make run          # or: ./start.sh
```

Open `http://127.0.0.1:7070`. **No account is required** — pick *Open my vault*
and you are in local-only mode. Notes live under `~/akaion-brain/` as plain
markdown.

## 4. Configure

```bash
akaion init       # writes ~/.akaion/config.yaml
akaion status     # config, vault stats, connection state
```

The default configuration is local-first: `cloud.enabled: false`, so the runner
never contacts a remote host until you ask it to. See
[Configuration](configuration.md) for every key, and read the warning about
allow-lists before relying on the policy.

## 5. Connect to the cloud — optional

```bash
akaion login        # opens a browser for Google sign-in
akaion cloud enable
akaion sync push --all-pending
```

Sync is **push-only, per note, on your command**. Cloud content is never written
back into your vault.

To point at your own backend instead of Akaion's, set `AKAION_API_BASE` and
implement three endpoints — see [Self-hosting](../index.md#start-here) in the
README.

## Commands

```bash
akaion login / logout           # cloud credentials
akaion init                     # create the configuration
akaion run                      # start the daemon and local UI
akaion run --once --task "…"    # execute a single task
akaion run --no-cloud           # force local-only for this run
akaion run --port 7171          # serve the local API elsewhere
akaion status                   # config, vault, connection
akaion logs -f                  # follow the log
akaion config                   # show, edit or reset the configuration
akaion dashboard                # interactive terminal dashboard
akaion version

akaion note add "title"         # create a note ($EDITOR, --stdin or --from-file)
akaion note list                # list notes, filterable by sync status
akaion note show <id|prefix>    # metadata and content
akaion note edit <id|prefix>    # edit; a synced note returns to pending
akaion note delete <id|prefix>
akaion note search "query"      # full-text search

akaion sync status              # what is local, pending, synced or failed
akaion sync push --all-pending  # push every pending note
akaion sync push --id <id>      # push specific notes
akaion sync push --dry-run      # show what would happen

akaion cloud enable / disable   # turn cloud sync on or off
akaion cloud status
```

Every command takes `--help`.

## Running the tests

```bash
make check        # lint · types · architectural contracts · tests
make test         # tests only
make test-cov     # with a coverage report
```

`make check` is exactly what CI runs. No credentials, no network.

## Building the desktop app

The desktop app is a Tauri 2 shell wrapping the Python daemon as a PyInstaller
sidecar.

```bash
./scripts/build-sidecar.sh          # PyInstaller → ui/src-tauri/binaries/
cd ui && npm install && npm run tauri:build
#   → src-tauri/target/release/bundle/dmg/Akaion Runner_<ver>_<arch>.dmg
```

Prerequisites: the [Rust toolchain](https://rustup.rs), Node 18+, and a venv
created by `make setup`.

For UI development with hot reload against the real sidecar:

```bash
./start.sh --tauri-dev
```

Windows and Linux bundles are produced by CI rather than locally — see
[Releasing](../reference/releasing.md).

## Where to go next

- [Configuration](configuration.md) — every key, and what the policy really does
- [Architecture as built](../design/architecture.md) — how the pieces fit
- [Research](../research/index.md) — what is not built yet, and how we will measure it
