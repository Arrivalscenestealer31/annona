#!/usr/bin/env bash
# Ad-hoc sign the macOS app bundle, then build the .dmg around the signed copy.
#
# Why this exists, in order of discovery:
#
# 1. Tauri's default leaves a *linker-signed* bundle: `Info.plist=not bound`,
#    `Sealed Resources=none`. That is fine locally and fatal once the file
#    carries a quarantine flag — macOS reports the app as **damaged** and offers
#    only "Move to Trash". Users downloading v0.1.0 hit exactly this.
#
# 2. `bundle.macOS.signingIdentity: "-"` fixes the seal and breaks the app a
#    different way: it signs *nested* binaries too, including the PyInstaller
#    sidecar. A onefile sidecar extracts its own Python.framework at runtime, and
#    that framework still carries the signature PyInstaller gave it, so the
#    loader refuses it:
#
#        Failed to load Python shared library ... mapping process and mapped
#        file (non-platform) have different Team IDs
#
#    The window opens and the daemon never starts.
#
# 3. Signing the bundle *without* `--deep` does both jobs: resources are sealed,
#    and the sidecar keeps the self-consistent signature PyInstaller produced.
#    Verified: `codesign --verify --strict` passes, Gatekeeper's verdict becomes
#    the recoverable "rejected" (unidentified developer) rather than an invalid
#    signature, and the daemon comes up.
#
# The .dmg is then built here rather than by Tauri, because Tauri creates the
# .app and the .dmg in one pass — there is no point in between at which the
# bundle can be signed.
#
# Usage: macos-sign-and-dmg.sh <target-triple> [version]

set -euo pipefail

TARGET="${1:?usage: macos-sign-and-dmg.sh <target-triple> [version]}"
VERSION="${2:-$(python3 -c "import json;print(json.load(open('ui/src-tauri/tauri.conf.json'))['version'])")}"
IDENTITY="${MACOS_SIGNING_IDENTITY:--}"

BUNDLE_DIR="ui/src-tauri/target/${TARGET}/release/bundle"
APP="${BUNDLE_DIR}/macos/Annona.app"

[ -d "$APP" ] || { echo "::error::no app bundle at $APP — build with --bundles app first" >&2; exit 1; }

echo "→ signing $APP with identity '${IDENTITY}' (no --deep, on purpose)"
codesign --force --sign "$IDENTITY" "$APP"
codesign --verify --strict "$APP"
codesign -dv --verbose=2 "$APP" 2>&1 | grep -E "Signature|Sealed Resources|Info.plist"

# Arch label matching Tauri's own naming, so the release assets and every
# download link on the site keep the names they already have.
case "$TARGET" in
  aarch64-apple-darwin) ARCH="aarch64" ;;
  x86_64-apple-darwin)  ARCH="x64" ;;
  *) echo "::error::unexpected target $TARGET" >&2; exit 1 ;;
esac

DMG="${BUNDLE_DIR}/dmg/Annona_${VERSION}_${ARCH}.dmg"
STAGE="$(mktemp -d)/Annona"
mkdir -p "$STAGE" "${BUNDLE_DIR}/dmg"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

rm -f "$DMG"
echo "→ building $DMG"
hdiutil create -volname "Annona" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
rm -rf "$(dirname "$STAGE")"

echo "→ done: $DMG"
