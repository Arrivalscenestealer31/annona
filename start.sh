#!/bin/bash

# Akaion Runner - Startup Script
# Usa sempre l'interprete del venv direttamente per evitare conflitti con alias shell

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$ROOT/env/bin/python3"

# ── Env profile loader ────────────────────────────────────────────────────────
# RUNNER_ENV=prod|dev (default prod) → sorgenta .env.<profile>. Le variabili
# gia' settate in shell hanno precedenza sul file (non veniamo sovrascritti).
RUNNER_ENV="${RUNNER_ENV:-prod}"
ENV_FILE="$ROOT/.env.$RUNNER_ENV"
if [ -f "$ENV_FILE" ]; then
    # set -a: ogni var assegnata viene esportata; set +a la disattiva dopo.
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
    echo "Loaded profile: $RUNNER_ENV  ($ENV_FILE)"
else
    echo "WARN: profile file $ENV_FILE not found — proceeding with shell env only."
fi

echo "ENVIRONMENT=${ENVIRONMENT:-unset}  AKAION_API_BASE=${AKAION_API_BASE:-unset}  AKAION_HOME=${AKAION_HOME:-$HOME/.akaion}"

# ── Mode: --tauri-dev → hot-reload Tauri shell against the real Python sidecar
for arg in "$@"; do
    if [ "$arg" = "--tauri-dev" ]; then
        echo "Launching Tauri dev shell (UI hot-reload + Python sidecar)..."
        cd "$ROOT/ui"
        if [ ! -d node_modules ]; then npm install; fi
        # Make sure the sidecar binary exists before tauri dev tries to bundle it
        TRIPLE=""
        case "$(uname -s)/$(uname -m)" in
            Darwin/arm64)  TRIPLE="aarch64-apple-darwin" ;;
            Darwin/x86_64) TRIPLE="x86_64-apple-darwin"  ;;
            Linux/x86_64)  TRIPLE="x86_64-unknown-linux-gnu" ;;
        esac
        if [ -n "$TRIPLE" ] && [ ! -f "$ROOT/ui/src-tauri/binaries/akaion-runner-${TRIPLE}" ]; then
            echo "Sidecar binary missing for $TRIPLE — building it now..."
            (cd "$ROOT" && ./scripts/build-sidecar.sh)
        fi
        exec npm run tauri:dev
    fi
done

echo "Starting Akaion Runner..."

if [ ! -f "$PYTHON" ]; then
    echo "Virtual environment not found. Creating..."
    python3 -m venv "$ROOT/env"
    "$ROOT/env/bin/pip" install -r "$ROOT/requirements.txt" -q
fi

# First-time init: create local config + vault structure (NO cloud login).
# Cloud sync is opt-in via `akaion login` or the UI "Sincronizza" button.
AKAION_CONFIG_DIR="${AKAION_HOME:-$HOME/.akaion}"
if [ ! -d "$AKAION_CONFIG_DIR" ]; then
    echo "First-time setup: initializing local config in $AKAION_CONFIG_DIR ..."
    "$PYTHON" "$ROOT/cli.py" init --no-interactive || true
fi

# ── Web UI build ──────────────────────────────────────────────────────────────
# Build ui/dist if missing (or if AKAION_UI_REBUILD=1 / --rebuild-ui passed).
REBUILD_UI=0
for arg in "$@"; do
    if [ "$arg" = "--rebuild-ui" ]; then
        REBUILD_UI=1
    fi
done
if [ "${AKAION_UI_REBUILD:-0}" = "1" ]; then
    REBUILD_UI=1
fi

if [ -f "$ROOT/ui/package.json" ]; then
    NEEDS_BUILD=0
    if [ ! -f "$ROOT/ui/dist/index.html" ]; then
        NEEDS_BUILD=1
    fi
    if [ "$REBUILD_UI" = "1" ]; then
        NEEDS_BUILD=1
    fi

    if [ "$NEEDS_BUILD" = "1" ]; then
        if command -v npm >/dev/null 2>&1; then
            echo "Building web UI..."
            (
                cd "$ROOT/ui" && \
                if [ ! -d node_modules ]; then npm install --silent; fi && \
                npm run build
            ) || echo "WARN: UI build failed — daemon will run API-only."
        else
            echo "WARN: node/npm not installed — skipping UI build. Install Node 18+ to enable web UI."
        fi
    else
        echo "Web UI already built (ui/dist)."
    fi
fi

# Strip UI-specific flags before forwarding the rest to the runner
RUNNER_ARGS=()
for arg in "$@"; do
    if [ "$arg" != "--rebuild-ui" ]; then
        RUNNER_ARGS+=("$arg")
    fi
done

PORT="${PORT:-7070}"
BRAIN_DIR="${BRAIN_DIR:-$HOME/akaion-brain}"

echo "Port: $PORT  Brain: $BRAIN_DIR"
echo "UI: http://127.0.0.1:$PORT"
exec "$PYTHON" "$ROOT/cli.py" run --port "$PORT" --brain-dir "$BRAIN_DIR" "${RUNNER_ARGS[@]}"
