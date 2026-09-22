#!/bin/zsh
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  echo "Run setup.sh first."
  read "?Press Enter to close."
  exit 1
fi
exec .venv/bin/python -m anime_dubber.gui
