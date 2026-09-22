from __future__ import annotations

import sys
from argparse import ArgumentParser
from pathlib import Path

from .core import (
    Config,
    CommandRunner,
    PipelineError,
    analyze_only,
    doctor,
    list_macos_voices,
    run_pipeline,
)


def add_common(r: ArgumentParser) -> None:
    r.add_argument("source", help="YouTube URL or local video file")
    r.add_argument("-o", "--output", default=str(Path.home() / "Movies" / "AnimeDubber"))
    r.add_argument("--series-id", default="", help="Use the same ID across episodes to keep character voices consistent")
    r.add_argument("--max-speakers", type=int, default=12)
    r.add_argument("--speaker-threshold", type=float, default=0.0, help="0=automatic; higher values create more speaker clusters")
    r.add_argument("--speaker-backend", choices=["auto", "ecapa", "acoustic"], default="auto", help="auto prefers ECAPA and falls back to built-in acoustic clustering")
    r.add_argument("--demucs-device", choices=["auto", "mps", "cpu"], default="auto")
    r.add_argument("--no-resume", action="store_true")
    r.add_argument("--force", action="store_true")


def build_parser() -> ArgumentParser:
    p = ArgumentParser(
        prog="anime-dubber",
        description="Multi-character Chinese anime/manhua-drama English dubbing on Apple Silicon while preserving music/SFX.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", help="Generate subtitles or a multi-character English dub")
    add_common(r)
    r.add_argument("--mode", choices=["subtitles", "dub"], default="dub")
    r.add_argument("--translation", choices=["llm", "whisper"], default="llm")
    r.add_argument("--tts", dest="tts_engine", choices=["macos", "elevenlabs"], default="macos")
    r.add_argument("--voice", default="", help="Fallback macOS voice. Multi-character mode assigns voices automatically.")
    r.add_argument("--tts-rate", type=int, default=210)
    r.add_argument("--context", default="")
    r.add_argument("--chunk-seconds", type=int, default=120)
    r.add_argument("--background-volume", type=float, default=1.0)
    r.add_argument("--dub-volume", type=float, default=1.15)
    r.add_argument("--no-ducking", action="store_true")
    r.add_argument("--single-voice", action="store_true", help="Disable character detection and use one voice")
    r.add_argument("--clean-work", action="store_true")
    r.add_argument("--elevenlabs-voice-id", default="JBFqnCBsd6RMkjVDRZzb")
    r.add_argument("--elevenlabs-model", default="eleven_v3")
    r.add_argument("--elevenlabs-api-key", default="", help="Prefer ELEVENLABS_API_KEY env var to keep keys out of shell history")

    a = sub.add_parser("analyze", help="Analyze speakers/characters without generating the full dub")
    add_common(a)

    sub.add_parser("doctor", help="Check programs and Python packages")
    sub.add_parser("voices", help="List installed macOS TTS voices")
    return p


def make_config(args, *, analysis=False) -> Config:
    return Config(
        source=args.source,
        output_dir=Path(args.output),
        mode=getattr(args, "mode", "dub"),
        translation=getattr(args, "translation", "llm"),
        tts_engine=getattr(args, "tts_engine", "macos"),
        voice=getattr(args, "voice", ""),
        tts_rate=getattr(args, "tts_rate", 210),
        context=(getattr(args, "context", "") or Config.__dataclass_fields__["context"].default),
        keep_work=not getattr(args, "clean_work", False),
        resume=not args.no_resume,
        force=args.force,
        demucs_device=args.demucs_device,
        chunk_seconds=getattr(args, "chunk_seconds", 120),
        background_volume=getattr(args, "background_volume", 1.0),
        dub_volume=getattr(args, "dub_volume", 1.15),
        ducking=not getattr(args, "no_ducking", False),
        elevenlabs_api_key=getattr(args, "elevenlabs_api_key", ""),
        elevenlabs_voice_id=getattr(args, "elevenlabs_voice_id", "JBFqnCBsd6RMkjVDRZzb"),
        elevenlabs_model_id=getattr(args, "elevenlabs_model", "eleven_v3"),
        multi_character=not getattr(args, "single_voice", False),
        max_speakers=max(2, int(args.max_speakers)),
        speaker_threshold=max(0.0, float(args.speaker_threshold)),
        series_id=args.series_id.strip(),
        speaker_backend=args.speaker_backend,
    )



def cli_progress(msg: str) -> None:
    if msg.startswith("__DOWNLOAD_PROGRESS__|"):
        parts = msg.split("|")
        try:
            pct = float(parts[1])
        except Exception:
            pct = 0.0
        speed = parts[2] if len(parts) > 2 else ""
        eta = parts[3] if len(parts) > 3 else ""
        attempt = parts[5] if len(parts) > 5 else "1"
        attempts = parts[6] if len(parts) > 6 else "1"
        extra = []
        if speed and speed not in {"Unknown", "N/A", "done"}:
            extra.append(speed)
        if eta and eta not in {"Unknown", "N/A", "0", "00:00"}:
            extra.append(f"ETA {eta}")
        suffix = (" | " + " | ".join(extra)) if extra else ""
        print(f"\rDownloading [{attempt}/{attempts}] {pct:5.1f}%{suffix}   ", end="", flush=True)
        if pct >= 100:
            print()
        return
    print(msg)

def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        ok, lines = doctor()
        print("\n".join(lines))
        return 0 if ok else 2
    if args.command == "voices":
        voices = list_macos_voices()
        if not voices:
            print("No macOS voices found (run this on macOS).")
            return 1
        print("\n".join(voices))
        return 0

    config = make_config(args, analysis=args.command == "analyze")
    runner = CommandRunner(cli_progress)
    try:
        results = analyze_only(config, cli_progress, runner) if args.command == "analyze" else run_pipeline(config, cli_progress, runner)
    except KeyboardInterrupt:
        runner.cancel(); print("Cancelled.", file=sys.stderr); return 130
    except (PipelineError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr); return 1

    print("\nOutputs:")
    for k, v in results.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
