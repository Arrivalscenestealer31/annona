#!/usr/bin/env bash
# Build the annona Python daemon as a PyInstaller onefile binary,
# then rename it to the Tauri sidecar convention:
#     ui/src-tauri/binaries/annona-<rust-target-triple>[.exe]
#
# Usage: ./scripts/build-sidecar.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# --- Resolve target triple (matches what Tauri expects) ----------------------
UNAME_S="$(uname -s)"
UNAME_M="$(uname -m)"
EXE_EXT=""
case "$UNAME_S" in
  Darwin)
    case "$UNAME_M" in
      arm64)  TRIPLE="aarch64-apple-darwin" ;;
      x86_64) TRIPLE="x86_64-apple-darwin"  ;;
      *) echo "unsupported macOS arch: $UNAME_M" >&2; exit 1 ;;
    esac
    ;;
  Linux)
    case "$UNAME_M" in
      x86_64) TRIPLE="x86_64-unknown-linux-gnu" ;;
      aarch64) TRIPLE="aarch64-unknown-linux-gnu" ;;
      *) echo "unsupported linux arch: $UNAME_M" >&2; exit 1 ;;
    esac
    ;;
  MINGW*|MSYS*|CYGWIN*)
    TRIPLE="x86_64-pc-windows-msvc"
    EXE_EXT=".exe"
    ;;
  *)
    echo "unsupported OS: $UNAME_S" >&2; exit 1 ;;
esac

# --- Locate Python venv ------------------------------------------------------
if [ -x "$ROOT/env/bin/python" ]; then
  PY="$ROOT/env/bin/python"
  PYI="$ROOT/env/bin/pyinstaller"
elif [ -x "$ROOT/env/bin/python3" ]; then
  PY="$ROOT/env/bin/python3"
  PYI="$ROOT/env/bin/pyinstaller"
else
  echo "venv not found at $ROOT/env — create it with 'python3 -m venv env && pip install -r requirements.txt'" >&2
  exit 1
fi

if [ ! -x "$PYI" ]; then
  echo "Installing PyInstaller into venv..."
  "$PY" -m pip install --quiet pyinstaller
fi

# --- Build UI first (sidecar bundles ui/dist) --------------------------------
if [ -f "$ROOT/ui/package.json" ]; then
  if [ ! -d "$ROOT/ui/node_modules" ]; then
    (cd "$ROOT/ui" && npm install --silent)
  fi
  if [ ! -f "$ROOT/ui/dist/index.html" ] || [ "${REBUILD_UI:-0}" = "1" ]; then
    echo "Building UI (vite)..."
    (cd "$ROOT/ui" && npm run build)
  else
    echo "UI dist already present (set REBUILD_UI=1 to force rebuild)."
  fi
fi

# --- Run PyInstaller ---------------------------------------------------------
TMP_DIST="$ROOT/ui/src-tauri/binaries/_tmp"
WORK="$ROOT/build/work"
mkdir -p "$TMP_DIST" "$WORK"

echo "Running PyInstaller (this can take a minute)..."
"$PYI" "$ROOT/runner.spec" \
  --distpath "$TMP_DIST" \
  --workpath "$WORK" \
  --clean --noconfirm

SRC_BIN="$TMP_DIST/annona${EXE_EXT}"
DEST_BIN="$ROOT/ui/src-tauri/binaries/annona-${TRIPLE}${EXE_EXT}"

if [ ! -f "$SRC_BIN" ]; then
  echo "PyInstaller output not found at $SRC_BIN" >&2
  exit 1
fi

mkdir -p "$(dirname "$DEST_BIN")"
mv -f "$SRC_BIN" "$DEST_BIN"
chmod +x "$DEST_BIN"
rm -rf "$TMP_DIST"

SIZE=$(du -h "$DEST_BIN" | awk '{print $1}')
echo ""
echo "Sidecar built: $DEST_BIN  ($SIZE)"
echo "Triple:        $TRIPLE"
