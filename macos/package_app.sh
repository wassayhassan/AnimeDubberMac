#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PKG="$SCRIPT_DIR/AnimeDubberApp"
DIST="$ROOT/dist"
APP="$DIST/AnimeDubber.app"
CONTENTS="$APP/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"
BACKEND="$RESOURCES/backend"

EMBED_VENV=1
INSTALL=0
OPEN_APP=0
SIGN=1

for arg in "$@"; do
  case "$arg" in
    --no-embed-venv) EMBED_VENV=0 ;;
    --install) INSTALL=1 ;;
    --open) OPEN_APP=1 ;;
    --no-sign) SIGN=0 ;;
    --help)
      cat <<'EOF'
Usage: ./macos/package_app.sh [options]

Options:
  --no-embed-venv  Build a lightweight app bundle for CI/development.
  --install        Copy the finished app to ~/Applications/AnimeDubber.app.
  --open           Open the app after packaging/installing.
  --no-sign        Skip local ad-hoc code signing.
EOF
      exit 0
      ;;
  esac
done

if ! command -v swift >/dev/null 2>&1; then
  echo "ERROR: Swift is required. Install Xcode Command Line Tools with: xcode-select --install"
  exit 1
fi

if [[ "$EMBED_VENV" -eq 1 && ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "ERROR: .venv is missing. Run ./setup.sh first, or use --no-embed-venv."
  exit 1
fi

VERSION="$("$ROOT/.venv/bin/python" -c 'import anime_dubber; print(anime_dubber.__version__)' 2>/dev/null || echo "4.0.0a5")"
SHORT_VERSION="${VERSION%%a*}"

echo "Building SwiftUI app (release)…"
swift build -c release --package-path "$PKG"
BIN_DIR="$(swift build -c release --package-path "$PKG" --show-bin-path)"
BIN="$BIN_DIR/AnimeDubberApp"
if [[ ! -x "$BIN" ]]; then
  echo "ERROR: Swift build completed but executable was not found at $BIN"
  exit 1
fi

echo "Assembling $APP…"
rm -rf "$APP"
mkdir -p "$MACOS" "$BACKEND"
cp "$BIN" "$MACOS/AnimeDubber"
chmod +x "$MACOS/AnimeDubber"

ditto "$ROOT/anime_dubber" "$BACKEND/anime_dubber"
cp "$ROOT/requirements.txt" "$BACKEND/requirements.txt"
cp "$ROOT/requirements-cross-platform.txt" "$BACKEND/requirements-cross-platform.txt"
cp "$ROOT/verify_source.py" "$BACKEND/verify_source.py"
find "$BACKEND" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
find "$BACKEND" -name '*.pyc' -delete 2>/dev/null || true

if [[ "$EMBED_VENV" -eq 1 ]]; then
  echo "Embedding the existing Python environment (this is the large part of the app)…"
  ditto "$ROOT/.venv" "$BACKEND/.venv"
fi

cat > "$CONTENTS/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleExecutable</key>
  <string>AnimeDubber</string>
  <key>CFBundleIdentifier</key>
  <string>com.animedubber.app</string>
  <key>CFBundleDisplayName</key>
  <string>AnimeDubber</string>
  <key>CFBundleName</key>
  <string>AnimeDubber</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>$SHORT_VERSION</string>
  <key>CFBundleVersion</key>
  <string>405</string>
  <key>LSMinimumSystemVersion</key>
  <string>14.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>NSSupportsAutomaticGraphicsSwitching</key>
  <true/>
</dict>
</plist>
EOF

if [[ "$SIGN" -eq 1 ]]; then
  echo "Applying local ad-hoc signature…"
  codesign --force --deep --sign - "$APP"
fi

TARGET="$APP"
if [[ "$INSTALL" -eq 1 ]]; then
  mkdir -p "$HOME/Applications"
  TARGET="$HOME/Applications/AnimeDubber.app"
  rm -rf "$TARGET"
  ditto "$APP" "$TARGET"
  echo "Installed: $TARGET"
else
  echo "Built: $APP"
fi

if [[ "$OPEN_APP" -eq 1 ]]; then
  open "$TARGET"
fi

echo
echo "AnimeDubber is ready."
echo "Models remain in the normal Hugging Face / ML caches and are not duplicated inside the app."
