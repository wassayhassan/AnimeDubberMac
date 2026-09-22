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
        p.add_argument("--translation", choices=["llm", "whisper"], default="llm")
        p.add_argument("--tts", choices=["macos", "elevenlabs"], default="macos")
        p.add_argument("--voice", default="")
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

    run = sub.add_parser("run", help="Generate subtitles or an English dub")
    add_job_args(run)
    run.add_argument("--subtitles-only", action="store_true")

    analyze = sub.add_parser("analyze", help="Analyze characters and write the character map")
    add_job_args(analyze)

    caps = sub.add_parser("capabilities", help="Show detected platform/provider capabilities")
    caps.add_argument("--json", action="store_true")

    return parser


def _payload(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "source": args.source,
        "output_dir": str(Path(args.output).expanduser()),
        "series_id": args.series_id,
        "mode": "subtitles" if getattr(args, "subtitles_only", False) else "dub",
        "translation": args.translation,
        "tts_engine": args.tts,
        "voice": args.voice,
        "tts_rate": args.rate,
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
