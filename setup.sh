#!/bin/zsh
set -euo pipefail
cd "$(dirname "$0")"

APP_VERSION="3.6.0"
echo "AI Anime English Dubber v${APP_VERSION} — setup"
echo "========================================"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "ERROR: This build targets macOS."
  exit 1
fi
if [[ "$(uname -m)" != "arm64" ]]; then
  echo "ERROR: This build requires an Apple Silicon Mac (M1/M2/M3/M4/M5...)."
  exit 1
fi
if ! command -v brew >/dev/null 2>&1; then
  echo "ERROR: Homebrew is required. Install it from https://brew.sh and run this setup again."
  exit 1
fi

echo "Installing system dependencies (safe to re-run)…"
brew install ffmpeg yt-dlp deno python@3.11
if brew info python-tk@3.11 >/dev/null 2>&1; then
  brew install python-tk@3.11
else
  brew install python-tk
fi

PY="$(brew --prefix python@3.11)/bin/python3.11"
if [[ ! -x "$PY" ]]; then
  echo "ERROR: Could not locate Homebrew Python 3.11 at: $PY"
  exit 1
fi

echo "Running source-code preflight BEFORE Python package installation…"
"$PY" verify_source.py

echo "Creating Python 3.11 virtual environment…"
if [[ -d .venv ]]; then
  VENV_VER="$(.venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
  if [[ "$VENV_VER" != "3.11" ]]; then
    echo "Existing virtual environment uses Python $VENV_VER; rebuilding it with Python 3.11."
    rm -rf .venv
  fi
fi

"$PY" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

echo "Installing a current app-local yt-dlp build (avoids stale PATH copies)…"
# YouTube delivery changes frequently. Master currently contains fixes newer
# than some stable/Homebrew builds. If GitHub is temporarily unreachable,
# fall back to the newest PyPI prerelease/stable build.
if ! python -m pip install --upgrade "yt-dlp[default,curl-cffi] @ https://github.com/yt-dlp/yt-dlp/archive/master.tar.gz"; then
  echo "WARNING: Could not install yt-dlp master from GitHub; falling back to PyPI."
  python -m pip install --upgrade --pre "yt-dlp[default,curl-cffi]"
fi
echo "App-local yt-dlp version:"
python -m yt_dlp --version

echo "Installing optional high-accuracy speaker encoder…"
if ! python -m pip install "speechbrain>=1.0,<2"; then
  echo "WARNING: SpeechBrain could not be installed. v3.1 will still work using its built-in acoustic speaker clustering fallback."
fi

echo "Running post-install source preflight…"
python verify_source.py

echo "Running bundled regression/integration tests…"
python -m unittest discover -s tests -v

echo "Import-checking GUI modules…"
python - <<'PYIMPORT'
import anime_dubber
import anime_dubber.core
import anime_dubber.characters
import anime_dubber.gui
print("Python imports: OK")
PYIMPORT

echo "Running system check…"
python - <<'PYDOCTOR'
from anime_dubber.core import doctor
ok, lines = doctor()
for line in lines:
    print(line)
if not ok:
    print("WARNING: System check reported one or more items that may need attention.")
PYDOCTOR

if command -v xattr >/dev/null 2>&1; then
  echo "Clearing the macOS quarantine attribute from this app folder (you explicitly chose to run setup.sh)…"
  xattr -dr com.apple.quarantine "$PWD" 2>/dev/null || true
fi

echo ""
echo "Setup complete."
echo "Launch: double-click 'Run GUI.command'"
