DubCanvas v4 alpha

macOS:
  1. /bin/zsh setup.sh
  2. Open /Applications/DubCanvas.app

Rebuild the native app:
  /bin/zsh macos/package_app.sh --install

CLI:
  .venv/bin/python -m dubcanvas --help

Windows/Linux:
  Use setup-cross-platform.ps1 or setup-cross-platform.sh
  and run the CLI.

The old Tkinter frontend has been removed.
The macOS app uses SwiftUI and launches the Python backend automatically.
