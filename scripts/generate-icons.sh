#!/usr/bin/env bash
# Regenerate the full Tauri icon set for akaion-app-runner.
#
# Pipeline:
#   1) Node script builds the 1024x1024 master (gradient bg + squircle + white
#      Akaion glyph extracted from Logo_Black.png + soft violet glow).
#   2) Tauri CLI fans the master out into .icns / .ico / Linux PNGs / iOS /
#      Android / Windows Store appx tiles.
#
# Requires: Node 18+, the PWA frontend node_modules (for `sharp`), and the
# `@tauri-apps/cli` already installed in ui/.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[icons] building master 1024x1024…"
node scripts/generate-icons.mjs

echo "[icons] fanning out via tauri icon…"
cd ui
npx tauri icon src-tauri/icons/icon-1024.png --output src-tauri/icons

echo "[icons] done. Preview with: open src-tauri/icons/icon.png"
