#!/usr/bin/env bash
set -euo pipefail

# Build PharmaSpot for macOS using PyInstaller
# Usage: ./scripts/build_macos.sh

REPO_ROOT="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$REPO_ROOT"

PY=python3
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "python3 not found. Install Python 3.11 or 3.12." >&2
  exit 1
fi

# Ensure icon (.icns) exists; generate from PNG if needed
ICNS="py_client/assets/pharmaspot-icon.icns"
PNG="py_client/assets/pharmaspot-icon.png"
if [[ ! -f "$ICNS" && -f "$PNG" && "$OSTYPE" == darwin* ]]; then
  echo "Generating .icns from $PNG ..."
  TMPSET="py_client/assets/pharmaspot-icon.iconset"
  rm -rf "$TMPSET"
  mkdir -p "$TMPSET"
  for sz in 16 32 64 128 256 512; do
    sips -z $sz $sz     "$PNG" --out "$TMPSET/icon_${sz}x${sz}.png" >/dev/null
    sips -z $((sz*2)) $((sz*2)) "$PNG" --out "$TMPSET/icon_${sz}x${sz}@2x.png" >/dev/null
  done
  iconutil -c icns -o "$ICNS" "$TMPSET"
  rm -rf "$TMPSET"
fi

VENV=".venv-mac-build"
if [[ ! -d "$VENV" ]]; then
  "$PY" -m venv "$VENV"
fi
# shellcheck disable=SC1090
source "$VENV/bin/activate"

python -m pip install --upgrade pip wheel setuptools
# Install client + backend deps, then PyInstaller
pip install -r py_client/requirements.txt\n# Try backend deps; if bcrypt 3.2.2 fails to build on macOS, retry without it and install a newer wheel\nif ! pip install -r python_backend/requirements.txt; then\n  echo 'Falling back: installing backend deps without bcrypt, then bcrypt>=4'\n  grep -v '^bcrypt' python_backend/requirements.txt > /tmp/backend-reqs-no-bcrypt.txt\n  pip install -r /tmp/backend-reqs-no-bcrypt.txt\n  pip install 'bcrypt>=4.0.1,<5'\nfi\npip install pyinstaller

# Clean previous builds
rm -rf build dist

# Use mac-specific spec that handles paths and icons cross-platform
pyinstaller PharmaSpot.macos.spec --noconfirm --clean --windowed

APP="dist/PharmaSpot.app"
if [[ -d "$APP" ]]; then
  echo "Built $APP"
  # Optional: create a DMG for distribution
  if command -v hdiutil >/dev/null 2>&1; then
    STAGE="dist/macos_stage"
    rm -rf "$STAGE" && mkdir -p "$STAGE"
    cp -R "$APP" "$STAGE/"
    hdiutil create -volname "PharmaSpot" -srcfolder "$STAGE" -ov -format UDZO "dist/PharmaSpot-macOS.dmg" >/dev/null
    echo "DMG created: dist/PharmaSpot-macOS.dmg"
  fi
else
  echo "Build finished but .app not found; check PyInstaller logs." >&2
  exit 2
fi

