#!/usr/bin/env bash
# Generate Tauri updater signing keys.
#
# Run this ONCE per project. After running:
#  1. Copy the printed public key into ui/src-tauri/tauri.conf.json under
#     plugins.updater.pubkey (replacing PLACEHOLDER_PUBLIC_KEY_…).
#  2. Add the private key + password to GitHub Secrets so release.yml can
#     sign release bundles in CI.
#
# Loss of the private key permanently breaks auto-update for already-installed
# clients (they will reject any new bundle). Back it up off-machine.

set -euo pipefail

KEY_DIR="${HOME}/.tauri"
KEY_FILE="${KEY_DIR}/akaion-runner.key"
PUB_FILE="${KEY_FILE}.pub"

mkdir -p "$KEY_DIR"

if [ -f "$KEY_FILE" ]; then
  echo "ERROR: ${KEY_FILE} already exists. Refusing to overwrite." >&2
  echo "If you really want to regenerate (and break updates for existing installs)," >&2
  echo "remove the file manually first." >&2
  exit 1
fi

# Resolve the Tauri CLI. Prefer the project's local install (ui/node_modules)
# so the version matches what's used during the actual release build.
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ -x "${REPO_ROOT}/ui/node_modules/.bin/tauri" ]; then
  TAURI_BIN="${REPO_ROOT}/ui/node_modules/.bin/tauri"
else
  echo "Tauri CLI not found locally; falling back to npx (will download)."
  TAURI_BIN="npx @tauri-apps/cli@latest"
fi

echo "Generating updater signing keys at: ${KEY_FILE}"
echo "You will be asked to set a password — DO NOT skip it."
echo ""

# `tauri signer generate -w <file>` writes the private key to <file> and prints
# the public key to stdout.
$TAURI_BIN signer generate -w "$KEY_FILE"

if [ ! -f "$PUB_FILE" ]; then
  echo "WARN: expected public key at ${PUB_FILE} not found." >&2
  echo "Newer Tauri CLI versions print the public key inline above." >&2
fi

cat <<EOF

──────────────────────────────────────────────────────────────────────────
Next steps:

1. Open ui/src-tauri/tauri.conf.json and replace
     "pubkey": "PLACEHOLDER_PUBLIC_KEY_GENERATED_BY_TAURI_SIGNER"
   with the public key printed above (or in ${PUB_FILE}).

2. Add to GitHub Secrets (repo Settings → Secrets and variables → Actions):
     TAURI_SIGNING_PRIVATE_KEY            = contents of ${KEY_FILE}
     TAURI_SIGNING_PRIVATE_KEY_PASSWORD   = the password you just set

3. Back up ${KEY_FILE} OFF this machine. If you lose it, every installed
   client will permanently reject future updates (signature mismatch).

4. NEVER commit ${KEY_FILE}. The repo .gitignore already excludes *.key.

5. Create SIGNING.md (local, gitignored) with the same info for future you.
──────────────────────────────────────────────────────────────────────────
EOF
