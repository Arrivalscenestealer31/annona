#!/usr/bin/env bash
# Build the `latest.json` manifest that tauri-plugin-updater fetches.
#
# Expected env (set by GitHub Actions):
#   GITHUB_REF_NAME    — tag name, e.g. "v0.2.0"
#   GITHUB_REPOSITORY  — "owner/repo", e.g. "Akaion-repos/akaion-app-runner"
#
# Usage: build-manifest.sh <assets-dir>
#
# Reads each platform's bundle + matching .sig from <assets-dir> and writes
# <assets-dir>/latest.json. The release-publish step uploads it alongside
# the bundles; the updater endpoint
#   https://github.com/<owner>/<repo>/releases/latest/download/latest.json
# resolves to the manifest of the most recent non-draft release.

set -euo pipefail

ASSETS_DIR="${1:-release-assets}"
VERSION="${GITHUB_REF_NAME#v}"
REPO_URL="https://github.com/${GITHUB_REPOSITORY}"
TAG="${GITHUB_REF_NAME}"

if [ ! -d "$ASSETS_DIR" ]; then
  echo "::error::assets dir not found: $ASSETS_DIR" >&2
  exit 1
fi

# Tauri 2 bundle filename conventions:
#   macOS (M-series): "Akaion Runner_<version>_aarch64.dmg"
#   macOS (Intel):    "Akaion Runner_<version>_x64.dmg"
#   Linux AppImage:   "Akaion Runner_<version>_amd64.AppImage"
#   Windows NSIS:     "Akaion Runner_<version>_x64-setup.exe"
# .deb has no updater path (apt handles updates), so we skip it.
declare -a PLATFORMS=(
  "darwin-aarch64|*aarch64.dmg"
  "darwin-x86_64|*x64.dmg"
  "linux-x86_64|*amd64.AppImage"
  "windows-x86_64|*x64-setup.exe"
)

NOTES="Akaion Runner ${VERSION}"
PUB_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Build platforms object piece by piece to keep the JSON valid even if a
# bundle is missing for some target.
PLATFORM_ENTRIES=""
for entry in "${PLATFORMS[@]}"; do
  plat="${entry%%|*}"
  pattern="${entry##*|}"

  # Find the bundle (exclude .sig files).
  file=$(find "$ASSETS_DIR" -maxdepth 1 -type f -name "$pattern" ! -name "*.sig" | head -n1 || true)
  if [ -z "$file" ]; then
    echo "::warning::no bundle for $plat (pattern: $pattern); skipping"
    continue
  fi

  sig_file="${file}.sig"
  if [ ! -f "$sig_file" ]; then
    echo "::warning::no signature for $file; skipping $plat — release will not auto-update for this platform"
    continue
  fi

  sig=$(tr -d '\n\r' < "$sig_file")
  fname=$(basename "$file")
  # URL-encode the filename (spaces → %20). GitHub release URLs accept either,
  # but the updater's HTTP client is strict.
  encoded=$(python3 -c "import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1]))" "$fname")
  url="${REPO_URL}/releases/download/${TAG}/${encoded}"

  if [ -n "$PLATFORM_ENTRIES" ]; then
    PLATFORM_ENTRIES="${PLATFORM_ENTRIES},"
  fi
  PLATFORM_ENTRIES="${PLATFORM_ENTRIES}
    \"${plat}\": {\"signature\": \"${sig}\", \"url\": \"${url}\"}"
done

if [ -z "$PLATFORM_ENTRIES" ]; then
  echo "::error::no signed bundles found — cannot publish updater manifest" >&2
  exit 1
fi

cat > "$ASSETS_DIR/latest.json" <<EOF
{
  "version": "${VERSION}",
  "notes": "${NOTES}",
  "pub_date": "${PUB_DATE}",
  "platforms": {${PLATFORM_ENTRIES}
  }
}
EOF

echo "Wrote ${ASSETS_DIR}/latest.json:"
cat "$ASSETS_DIR/latest.json"
