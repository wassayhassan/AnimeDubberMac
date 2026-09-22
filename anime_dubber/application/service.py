from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import subprocess
import sys
import threading
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from ..core import (
    CancelledError,
    CommandRunner,
    Config,
    DEFAULT_CONTEXT,
    DEFAULT_GLOSSARY,
    analyze_only,
    list_macos_voices,
    run_pipeline,
)
from .events import AppEvent, progress_to_event
from .jobs import JobRecord
from .project import ProjectStore, get_project as load_project, list_projects as list_project_manifests


EventSink = Callable[[AppEvent], None]


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def config_from_dict(payload: Dict[str, Any]) -> Config:
    """Build the current pipeline Config from the versioned UI/CLI schema.

    Both nested v4-style configuration and the existing flat Config shape are
    accepted so the backend can evolve without breaking cached callers.
    """
    data = dict(payload or {})
    audio = dict(data.get("audio") or {})
    speaker = dict(data.get("speaker_analysis") or {})
    tts = data.get("tts")
    tts = dict(tts) if isinstance(tts, dict) else {}
    translation = data.get("translation")
    translation = dict(translation) if isinstance(translation, dict) else {}
    asr = data.get("asr")
    asr = dict(asr) if isinstance(asr, dict) else {}

    source = str(data.get("source") or "").strip()
    output_dir = str(data.get("output_dir") or "").strip()
    if not source:
        raise ValueError("source is required")
    if not output_dir:
        raise ValueError("output_dir is required")

    asr_provider = str(asr.get("provider") or data.get("asr_provider") or "auto")

    translation_provider = str(
        translation.get("provider") or data.get("translation") or "auto"
    )
    if translation_provider in {"mlx_llm", "local_llm"}:
        translation_provider = "llm"
    elif translation_provider in {"whisper_direct", "whisper_translate"}:
        translation_provider = "whisper"

    tts_provider = str(tts.get("provider") or data.get("tts_engine") or "auto")
    if tts_provider == "macos_say":
        tts_provider = "macos"

    threshold = speaker.get("threshold", data.get("speaker_threshold", 0.0))
    if threshold is None:
        threshold = 0.0

    return Config(
        source=source,
        output_dir=Path(output_dir).expanduser(),
        mode=str(data.get("mode") or "dub"),
        asr_provider=asr_provider,
        faster_whisper_model=str(asr.get("model", data.get("faster_whisper_model", "large-v3")) or "large-v3"),
        faster_whisper_device=str(asr.get("device", data.get("faster_whisper_device", "auto")) or "auto"),
        faster_whisper_compute_type=str(asr.get("compute_type", data.get("faster_whisper_compute_type", "auto")) or "auto"),
        translation=translation_provider,
        ollama_url=str(translation.get("ollama_url", data.get("ollama_url", "http://127.0.0.1:11434")) or "http://127.0.0.1:11434"),
        ollama_model=str(translation.get("model", data.get("ollama_model", "qwen3:4b")) or "qwen3:4b"),
        tts_engine=tts_provider,
        voice=str(tts.get("fallback_voice", data.get("voice", "")) or ""),
        piper_model=str(tts.get("piper_model", data.get("piper_model", "")) or ""),
        piper_speaker=int(tts.get("piper_speaker", data.get("piper_speaker", -1))),
        tts_rate=int(tts.get("rate", data.get("tts_rate", 210))),
        context=str(data.get("context") or data.get("series_context") or DEFAULT_CONTEXT),
        glossary=dict(data.get("glossary") or DEFAULT_GLOSSARY),
        keep_work=bool(data.get("keep_work", True)),
        resume=bool(data.get("resume", True)),
        force=bool(data.get("force", False)),
        demucs_device=str(data.get("demucs_device") or "auto"),
        chunk_seconds=int(data.get("chunk_seconds", 120)),
        background_volume=float(audio.get("background_volume", data.get("background_volume", 1.0))),
        dub_volume=float(audio.get("dub_volume", data.get("dub_volume", 1.15))),
        ducking=bool(audio.get("ducking", data.get("ducking", False))),
        elevenlabs_api_key=str(tts.get("api_key", data.get("elevenlabs_api_key", "")) or ""),
        elevenlabs_voice_id=str(tts.get("voice_id", data.get("elevenlabs_voice_id", "JBFqnCBsd6RMkjVDRZzb")) or ""),
        elevenlabs_model_id=str(tts.get("model_id", data.get("elevenlabs_model_id", "eleven_v3")) or ""),
        multi_character=bool(speaker.get("enabled", data.get("multi_character", True))),
        max_speakers=max(2, int(speaker.get("max_speakers", data.get("max_speakers", 12)))),
        speaker_threshold=max(0.0, float(threshold)),
        series_id=str(data.get("series_id") or ""),
        speaker_backend=str(speaker.get("backend", data.get("speaker_backend", "auto")) or "auto"),
    )


class ApplicationService:
    def __init__(self, event_sink: Optional[EventSink] = None):
        self._event_sink = event_sink or (lambda _event: None)
        self._jobs: Dict[str, JobRecord] = {}
        self._project_stores: Dict[str, ProjectStore] = {}
        self._project_progress_buckets: Dict[str, int] = {}
        self._lock = threading.RLock()

    def _emit(self, event: AppEvent) -> None:
        self._event_sink(event)

    def capabilities(self) -> dict:
        system = platform.system()
        machine = platform.machine()
        mlx_ok = system == "Darwin" and machine == "arm64" and _module_available("mlx_whisper")
        mlx_lm_ok = system == "Darwin" and machine == "arm64" and _module_available("mlx_lm")
        faster_ok = _module_available("faster_whisper")
        piper_ok = bool(shutil.which("piper")) or _module_available("piper")
        ollama_ok = bool(shutil.which("ollama"))

        return {
            "platform": {"system": system, "machine": machine, "python": sys.version.split()[0]},
            "providers": {
                "asr": {
                    "mlx_whisper": mlx_ok,
                    "faster_whisper": faster_ok,
                },
                "translation": {
                    "mlx_llm": mlx_lm_ok,
                    "whisper_direct": mlx_ok or faster_ok,
                    "ollama": ollama_ok,
                },
                "tts": {
                    "macos": system == "Darwin" and bool(shutil.which("say")),
                    "piper": piper_ok,
                    "elevenlabs": True,
                },
                "stems": {
                    "demucs": _module_available("demucs"),
                },
            },
            "current_pipeline": {
                "engine": "v4_shared",
                "processing_supported": bool(
                    _module_available("demucs")
                    and (mlx_ok or faster_ok)
                    and (
                        (system == "Darwin" and bool(shutil.which("say")))
                        or piper_ok
                        or True
                    )
                ),
                "note": (
                    "Apple silicon can use MLX Whisper/MLX LLM/macOS voices. "
                    "Windows and Linux can use Faster-Whisper, Whisper-direct or Ollama translation, "
                    "and Piper or ElevenLabs TTS."
                ),
            },
        }

    def system_check(self) -> dict:
        caps = self.capabilities()
        checks = []
        for exe in ("ffmpeg", "ffprobe"):
            path = shutil.which(exe)
            checks.append({"name": exe, "ok": bool(path), "detail": path or "not found"})
        yt = shutil.which("yt-dlp") or shutil.which("yt_dlp")
        checks.append({"name": "yt-dlp", "ok": bool(yt), "detail": yt or "not found"})
        checks.append({
            "name": "demucs",
            "ok": bool(caps["providers"]["stems"]["demucs"]),
            "detail": "available" if caps["providers"]["stems"]["demucs"] else "not installed",
        })

        if platform.system() == "Darwin":
            checks.append({
                "name": "mlx-whisper",
                "ok": bool(caps["providers"]["asr"]["mlx_whisper"]),
                "detail": "available" if caps["providers"]["asr"]["mlx_whisper"] else "not installed",
            })
            checks.append({
                "name": "macOS voices",
                "ok": bool(caps["providers"]["tts"]["macos"]),
                "detail": "available" if caps["providers"]["tts"]["macos"] else "say not found",
            })
        else:
            checks.append({
                "name": "faster-whisper",
                "ok": bool(caps["providers"]["asr"]["faster_whisper"]),
                "detail": "available" if caps["providers"]["asr"]["faster_whisper"] else "install requirements-cross-platform.txt",
            })
            checks.append({
                "name": "Piper",
                "ok": bool(caps["providers"]["tts"]["piper"]),
                "detail": "available (voice model still required)" if caps["providers"]["tts"]["piper"] else "optional local TTS; install piper-tts or use ElevenLabs",
                "optional": True,
            })
            checks.append({
                "name": "Ollama",
                "ok": bool(caps["providers"]["translation"]["ollama"]),
                "detail": "available" if caps["providers"]["translation"]["ollama"] else "optional; Whisper direct translation works without it",
                "optional": True,
            })

        required = [x for x in checks if not x.get("optional")]
        base_ok = all(x["ok"] for x in required)
        return {"ok": base_ok, "checks": checks, "capabilities": caps}

    def list_voices(self) -> list[str]:
        if platform.system() != "Darwin":
            return []
        return list_macos_voices()

    def _normalized_config_dict(self, config: Config) -> dict:
        return _json_safe(asdict(config))

    def start_job(self, payload: Dict[str, Any], *, analysis: bool = False) -> str:
        config = config_from_dict(payload)
        job_id = "job_" + uuid.uuid4().hex[:12]
        record = JobRecord(
            id=job_id,
            kind="analyze" if analysis else "run",
            config=self._normalized_config_dict(config),
        )
        store = ProjectStore(config.output_dir, config.source)
        store.begin(job_id=job_id, kind=record.kind, config=record.config)
        with self._lock:
            self._jobs[job_id] = record
            self._project_stores[job_id] = store

        thread = threading.Thread(
            target=self._execute,
            args=(record, config, analysis),
            name=f"AnimeDubber-{job_id}",
            daemon=True,
        )
        thread.start()
        return job_id

    def run_sync(self, payload: Dict[str, Any], *, analysis: bool = False) -> dict:
        config = config_from_dict(payload)
        job_id = "job_" + uuid.uuid4().hex[:12]
        record = JobRecord(
            id=job_id,
            kind="analyze" if analysis else "run",
            config=self._normalized_config_dict(config),
        )
        store = ProjectStore(config.output_dir, config.source)
        store.begin(job_id=job_id, kind=record.kind, config=record.config)
        with self._lock:
            self._jobs[job_id] = record
            self._project_stores[job_id] = store
        self._execute(record, config, analysis)
        snapshot = self.get_job(job_id)
        if snapshot["status"] == "failed":
            raise RuntimeError(snapshot["error"] or "AnimeDubber job failed")
        if snapshot["status"] == "cancelled":
            raise CancelledError("Cancelled by user")
        return snapshot

    def _execute(self, record: JobRecord, config: Config, analysis: bool) -> None:
        from datetime import datetime, timezone

        record.status = "running"
        record.stage = "preparing"
        record.started_at = datetime.now(timezone.utc).isoformat()
        runner = CommandRunner()
        record.runner = runner
        store = self._project_stores.get(record.id)

        def progress(message: str) -> None:
            event = progress_to_event(message, record.id)
            if event.event in {"stage", "progress"}:
                stage = str(event.data.get("stage") or record.stage)
                record.stage = stage
                if store:
                    fraction = event.data.get("fraction")
                    should_write = event.event == "stage"
                    if isinstance(fraction, (int, float)):
                        bucket = int(max(0.0, min(1.0, float(fraction))) * 20)
                        old_bucket = self._project_progress_buckets.get(record.id)
                        if old_bucket != bucket:
                            self._project_progress_buckets[record.id] = bucket
                            should_write = True
                    if should_write:
                        store.update_stage(
                            stage=stage,
                            title=str(event.data.get("title") or ""),
                            progress=float(fraction) if isinstance(fraction, (int, float)) else None,
                        )
            self._emit(event)
            if not str(message).startswith("__DOWNLOAD_PROGRESS__|"):
                if store:
                    store.append_log(str(message))
                self._emit(AppEvent("log", {"level": "info", "message": str(message)}, record.id))

        runner.progress = progress
        self._emit(AppEvent("job_started", {"kind": record.kind}, record.id))

        try:
            # The application boundary is cross-platform now, while the legacy v3
            # implementation underneath it is still MLX/macOS-specific. Provider
            # replacement happens without changing the SwiftUI/CLI contracts.
            results = analyze_only(config, progress, runner) if analysis else run_pipeline(config, progress, runner)
            record.result = {str(k): str(v) for k, v in results.items()}
            record.status = "completed"
            record.stage = "completed"
            if store:
                store.finish(status="completed", artifacts=record.result)
            for kind, path in record.result.items():
                self._emit(AppEvent("artifact", {"kind": kind, "path": path}, record.id))
            self._emit(AppEvent("finished", {"status": "completed", "result": record.result}, record.id))
        except CancelledError as exc:
            record.status = "cancelled"
            record.stage = "cancelled"
            record.error = str(exc)
            if store:
                store.finish(status="cancelled", error=str(exc))
            self._emit(AppEvent("finished", {"status": "cancelled"}, record.id))
        except Exception as exc:
            record.status = "failed"
            record.stage = "failed"
            record.error = str(exc)
            if store:
                store.finish(status="failed", error=str(exc))
            self._emit(AppEvent("error", {"message": str(exc), "error_type": type(exc).__name__}, record.id))
            self._emit(AppEvent("finished", {"status": "failed"}, record.id))
        finally:
            record.ended_at = datetime.now(timezone.utc).isoformat()
            record.runner = None
            with self._lock:
                self._project_progress_buckets.pop(record.id, None)

    def cancel_job(self, job_id: str) -> bool:
        with self._lock:
            record = self._jobs.get(job_id)
        if not record:
            return False
        if record.runner:
            record.runner.cancel()
            return True
        return record.status in {"cancelled", "completed", "failed"}

    def get_job(self, job_id: str) -> dict:
        with self._lock:
            record = self._jobs.get(job_id)
            if not record:
                raise KeyError(job_id)
            return record.to_dict()

    def list_jobs(self) -> list[dict]:
        with self._lock:
            return [job.to_dict() for job in self._jobs.values()]

    def list_projects(self, output_dir: str) -> list[dict]:
        if not str(output_dir or "").strip():
            raise ValueError("output_dir is required")
        return list_project_manifests(Path(output_dir).expanduser())

    def get_project(self, output_dir: str, project_id: str) -> dict:
        if not str(output_dir or "").strip():
            raise ValueError("output_dir is required")
        if not str(project_id or "").strip():
            raise ValueError("project_id is required")
        return load_project(Path(output_dir).expanduser(), str(project_id))

    def list_character_maps(self, output_dir: str) -> list[dict]:
        if not str(output_dir or "").strip():
            raise ValueError("output_dir is required")
        from ..characters import list_character_maps
        return list_character_maps(Path(output_dir).expanduser())

    def get_characters(self, path: str) -> dict:
        if not str(path or "").strip():
            raise ValueError("path is required")
        from ..characters import character_map_for_ui
        return character_map_for_ui(Path(path).expanduser())

    def update_character(self, path: str, character_id: str, updates: Dict[str, Any]) -> dict:
        if not str(path or "").strip():
            raise ValueError("path is required")
        if not str(character_id or "").strip():
            raise ValueError("character_id is required")
        from ..characters import update_character_override
        saved = update_character_override(Path(path).expanduser(), character_id, updates)
        self._emit(AppEvent("character_updated", {"path": str(path), "character": saved}))
        return saved

    def preview_voice(self, voice: str, text: str, rate: int = 205) -> dict:
        if platform.system() != "Darwin" or not shutil.which("say"):
            raise RuntimeError("Voice preview currently requires macOS 'say'.")
        clean_text = str(text or "").strip() or "This is the selected character speaking in English."
        cmd = ["say", "-r", str(max(80, min(450, int(rate))))]
        clean_voice = str(voice or "").strip()
        if clean_voice:
            cmd += ["-v", clean_voice]
        cmd.append(clean_text)
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"started": True}
