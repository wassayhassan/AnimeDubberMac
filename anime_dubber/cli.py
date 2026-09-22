from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from . import __version__
from .application import AppEvent, ApplicationService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="animedubber",
        description="AnimeDubber command line interface",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="Check backend and provider availability")

    def add_job_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("source", help="YouTube URL or local video path")
        p.add_argument("-o", "--output", default=str(Path.cwd() / "AnimeDubberOutput"))
        p.add_argument("--series-id", default="")
        p.add_argument("--target-language", choices=["en", "es", "fr", "de", "ja"], default="en")
        p.add_argument("--dub-name", default="", help="Name of this dub version")
        p.add_argument(
            "--asr",
            choices=["auto", "mlx-whisper", "faster-whisper"],
            default="auto",
            help="Speech recognition backend. auto uses MLX on Apple silicon, Faster-Whisper elsewhere.",
        )
        p.add_argument("--faster-whisper-model", default="large-v3")
        p.add_argument("--faster-whisper-device", default="auto", help="auto, cpu, or cuda")
        p.add_argument("--faster-whisper-compute-type", default="auto")
        p.add_argument(
            "--translation",
            choices=["auto", "llm", "ollama", "whisper"],
            default="auto",
            help="auto uses MLX LLM when available, otherwise Whisper direct translation.",
        )
        p.add_argument("--ollama-url", default="http://127.0.0.1:11434")
        p.add_argument("--ollama-model", default="qwen3:4b")
        p.add_argument(
            "--tts",
            choices=["auto", "chatterbox", "kokoro", "macos", "piper", "elevenlabs"],
            default="auto",
            help="auto prefers Chatterbox, then Kokoro, then platform fallbacks.",
        )
        p.add_argument("--voice", default="")
        p.add_argument("--chatterbox-reference", default="", help="Optional voice reference clip you have permission to use")
        p.add_argument("--chatterbox-expressiveness", type=float, default=0.5)
        p.add_argument("--chatterbox-device", choices=["auto", "mps", "cuda", "cpu"], default="auto")
        p.add_argument("--chatterbox-standard", action="store_true", help="Use standard Chatterbox instead of Turbo")
        p.add_argument("--kokoro-voice", default="auto", help="Kokoro voice preset, e.g. af_heart or am_adam")
        p.add_argument("--piper-model", default="", help="Path to a Piper .onnx voice model")
        p.add_argument("--piper-speaker", type=int, default=-1, help="Optional Piper speaker id for multi-speaker models")
        p.add_argument("--rate", type=int, default=210)
        p.add_argument("--speaker-backend", choices=["auto", "ecapa", "acoustic"], default="auto")
        p.add_argument("--max-speakers", type=int, default=12)
        p.add_argument("--speaker-threshold", type=float, default=0.0)
        p.add_argument("--no-characters", action="store_true")
        p.add_argument("--no-resume", action="store_true")
        p.add_argument("--force", action="store_true")
        p.add_argument("--ducking", action="store_true")
        p.add_argument("--background-volume", type=float, default=1.0)
        p.add_argument("--dub-volume", type=float, default=1.15)
        p.add_argument("--elevenlabs-api-key", default="")
        p.add_argument("--json", action="store_true", help="Print machine-readable final result")

    run = sub.add_parser("run", help="Generate subtitles or a dub version")
    add_job_args(run)
    run.add_argument("--subtitles-only", action="store_true")

    analyze = sub.add_parser("analyze", help="Analyze characters and write the character map")
    add_job_args(analyze)

    caps = sub.add_parser("capabilities", help="Show detected platform/provider capabilities")
    caps.add_argument("--json", action="store_true")

    projects = sub.add_parser("projects", help="List source projects and their dub versions")
    projects.add_argument("-o", "--output", default=str(Path.cwd() / "AnimeDubberOutput"))
    create = sub.add_parser("new-project", help="Register a source video before processing")
    create.add_argument("source")
    create.add_argument("-o", "--output", default=str(Path.cwd() / "AnimeDubberOutput"))
    create.add_argument("--name", default="")
    create.add_argument("--series-id", default="")

    return parser


def _payload(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "source": args.source,
        "output_dir": str(Path(args.output).expanduser()),
        "series_id": args.series_id,
        "target_language": args.target_language,
        "dub_name": args.dub_name,
        "mode": "subtitles" if getattr(args, "subtitles_only", False) else "dub",
        "asr": {
            "provider": args.asr,
            "model": args.faster_whisper_model,
            "device": args.faster_whisper_device,
            "compute_type": args.faster_whisper_compute_type,
        },
        "translation": {
            "provider": args.translation,
            "ollama_url": args.ollama_url,
            "model": args.ollama_model,
        },
        "tts": {
            "provider": args.tts,
            "fallback_voice": args.voice,
            "chatterbox_reference_audio": args.chatterbox_reference,
            "chatterbox_expressiveness": args.chatterbox_expressiveness,
            "chatterbox_device": args.chatterbox_device,
            "chatterbox_turbo": not args.chatterbox_standard,
            "kokoro_voice": args.kokoro_voice,
            "piper_model": args.piper_model,
            "piper_speaker": args.piper_speaker,
            "rate": args.rate,
            "api_key": args.elevenlabs_api_key,
        },
        "speaker_backend": args.speaker_backend,
        "max_speakers": args.max_speakers,
        "speaker_threshold": args.speaker_threshold,
        "multi_character": not args.no_characters,
        "resume": not args.no_resume,
        "force": args.force,
        "ducking": args.ducking,
        "background_volume": args.background_volume,
        "dub_volume": args.dub_volume,
        "elevenlabs_api_key": args.elevenlabs_api_key,
        "chatterbox_reference_audio": args.chatterbox_reference,
        "chatterbox_expressiveness": args.chatterbox_expressiveness,
        "chatterbox_device": args.chatterbox_device,
        "chatterbox_turbo": not args.chatterbox_standard,
        "kokoro_voice": args.kokoro_voice,
        "piper_model": args.piper_model,
        "piper_speaker": args.piper_speaker,
    }


def _print_event(event: AppEvent) -> None:
    if event.event == "progress":
        fraction = event.data.get("fraction")
        title = event.data.get("title", "Working")
        if isinstance(fraction, (int, float)):
            print(f"\r{title}: {fraction * 100:5.1f}%", end="", flush=True)
        return

    if event.event == "log":
        message = str(event.data.get("message", ""))
        if message.startswith("__DOWNLOAD_PROGRESS__|"):
            return
        print(message)
    elif event.event == "error":
        print(f"ERROR: {event.data.get('message', 'Unknown error')}", file=sys.stderr)


def _doctor(service: ApplicationService) -> int:
    report = service.system_check()
    caps = report["capabilities"]
    p = caps["platform"]
    print(f"Platform: {p['system']} {p['machine']} · Python {p['python']}")
    for check in report["checks"]:
        mark = "✓" if check["ok"] else "✗"
        print(f"{mark} {check['name']}: {check['detail']}")
    note = caps["current_pipeline"]["note"]
    print(f"\nCurrent engine: {caps['current_pipeline']['engine']}")
    print(note)
    return 0 if report["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    service = ApplicationService(event_sink=_print_event)

    if args.command == "doctor":
        return _doctor(service)

    if args.command == "capabilities":
        caps = service.capabilities()
        if args.json:
            print(json.dumps(caps, indent=2))
        else:
            print(json.dumps(caps, indent=2))
        return 0

    if args.command == "projects":
        print(json.dumps(service.list_projects(args.output), indent=2))
        return 0
    if args.command == "new-project":
        print(json.dumps(service.create_project(args.output, args.source, args.name, args.series_id), indent=2))
        return 0

    analysis = args.command == "analyze"
    try:
        job = service.run_sync(_payload(args), analysis=analysis)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        print(json.dumps(job, indent=2))
    else:
        print()
        print("Completed.")
        for name, path in job.get("result", {}).items():
            print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
