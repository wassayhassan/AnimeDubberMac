from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional


def piper_executable() -> Optional[str]:
    found = shutil.which("piper")
    if found:
        return found
    # When callers run .venv/bin/python directly without activating the venv,
    # its scripts directory is not necessarily on PATH.
    name = "piper.exe" if os.name == "nt" else "piper"
    sibling = Path(sys.executable).resolve().parent / name
    return str(sibling) if sibling.exists() else None


def piper_command() -> list[str] | None:
    exe = piper_executable()
    if exe:
        return [exe]
    try:
        if importlib.util.find_spec("piper") is not None:
            return [sys.executable, "-m", "piper"]
    except Exception:
        pass
    return None


def piper_available() -> bool:
    return piper_command() is not None


def resolve_piper_model(explicit: str = "") -> Path:
    raw = (explicit or os.getenv("PIPER_MODEL", "")).strip()
    if not raw:
        raise RuntimeError(
            "Piper is selected but no voice model was configured. "
            "Pass --piper-model /path/to/voice.onnx or set PIPER_MODEL."
        )
    path = Path(raw).expanduser().resolve()
    if not path.exists():
        raise RuntimeError(f"Piper model does not exist: {path}")
    return path


def synthesize_piper(
    text: str,
    out_wav: Path,
    *,
    model_path: str,
    rate: int = 205,
    speaker: int | None = None,
    cancel_check: Callable[[], None] | None = None,
) -> None:
    """Synthesize with Piper through the stable CLI/stdin interface."""
    base_cmd = piper_command()
    if not base_cmd:
        raise RuntimeError(
            "Piper was not found. Install piper-tts in the environment "
            "or choose ElevenLabs/macOS TTS."
        )
    model = resolve_piper_model(model_path)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    if cancel_check:
        cancel_check()

    safe_rate = max(80, min(450, int(rate)))
    length_scale = max(0.55, min(1.80, 205.0 / safe_rate))
    cmd = [
        *base_cmd,
        "--model", str(model),
        "--output_file", str(out_wav),
        "--length_scale", f"{length_scale:.4f}",
    ]
    if speaker is not None:
        cmd += ["--speaker", str(int(speaker))]

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _stdout, stderr = proc.communicate(text + "\n")
    except BaseException:
        try:
            proc.terminate()
        except Exception:
            pass
        raise
    if cancel_check:
        cancel_check()
    if proc.returncode != 0:
        raise RuntimeError(f"Piper failed ({proc.returncode}): {(stderr or '')[-2000:]}")
    if not out_wav.exists() or out_wav.stat().st_size <= 44:
        raise RuntimeError("Piper completed without producing usable audio.")
