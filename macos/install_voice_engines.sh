#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

if [[ ! -x .venv/bin/python ]]; then
  echo "ERROR: AnimeDubber's .venv does not exist. Run ./setup.sh first."
  exit 1
fi

if command -v brew >/dev/null 2>&1; then
  echo "Installing Kokoro speech dependency espeak-ng…"
  brew install espeak-ng
else
  echo "WARNING: Homebrew was not found. Kokoro requires espeak-ng."
fi

PY="$ROOT/.venv/bin/python"
"$PY" -m pip install --upgrade pip setuptools wheel

echo
echo "Installing Kokoro…"
"$PY" -m pip install "kokoro>=0.9.4,<1" soundfile

echo
echo "Installing Chatterbox Turbo…"
echo "Chatterbox pins its compatible PyTorch/torchaudio versions, so this step can take a while."
if ! "$PY" -m pip install "chatterbox-tts>=0.1.7,<0.2"; then
  echo
  echo "WARNING: Chatterbox installation failed. Kokoro remains available."
  echo "AnimeDubber will automatically fall back to Kokoro/macOS voices."
fi

echo
echo "Voice provider status:"
"$PY" - <<'PY'
from anime_dubber.providers.tts import premium_voice_status
for name, ok in premium_voice_status().items():
    print(f"{'✓' if ok else '✗'} {name}")
PY

echo
echo "Running backend tests after voice-engine installation…"
"$PY" -m unittest discover -s tests -v

echo
if command -v swift >/dev/null 2>&1; then
  echo "Rebuilding the native app so its bundled backend includes the new voice engines…"
  /bin/zsh macos/package_app.sh --install
  echo "Updated the app at the location reported above."
else
  echo "Swift is not available. Rebuild the app later with:"
  echo "  /bin/zsh macos/package_app.sh --install"
fi
