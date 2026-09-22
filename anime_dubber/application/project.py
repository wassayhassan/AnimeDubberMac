from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from ..core import Config, source_key


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    return value


def _redacted_config(config: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(config)
    for key in ("elevenlabs_api_key", "api_key", "token", "password"):
        if key in data and data[key]:
            data[key] = "<redacted>"
    tts = data.get("tts")
    if isinstance(tts, dict):
        tts = dict(tts)
        if tts.get("api_key"):
            tts["api_key"] = "<redacted>"
        data["tts"] = tts
    return _safe(data)


def _atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


class ProjectStore:
    """Small durable manifest used by both SwiftUI and CLI.

    Heavy work stays in .anime_dubber_work; this directory is intentionally
    lightweight so the Projects screen can load without scanning media caches.
    """

    def __init__(self, output_dir: Path, source: str):
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.project_id = source_key(source)
        self.root = self.output_dir / ".anime_dubber_project"
        self.manifest_path = self.root / "projects" / f"{self.project_id}.json"
        self.log_path = self.root / "logs" / f"{self.project_id}.log"

    def load(self) -> dict:
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def begin(self, *, job_id: str, kind: str, config: Dict[str, Any]) -> dict:
        now = _now()
        old = self.load()
        created_at = old.get("created_at") or now
        runs = list(old.get("runs") or [])
        runs.append({
            "job_id": job_id,
            "kind": kind,
            "started_at": now,
            "status": "running",
        })
        runs = runs[-20:]

        payload = {
            "schema_version": 1,
            "project_id": self.project_id,
            "source": str(config.get("source") or ""),
            "series_id": str(config.get("series_id") or ""),
            "output_dir": str(self.output_dir),
            "status": "running",
            "stage": "preparing",
            "stage_title": "Preparing",
            "progress": None,
            "active_job_id": job_id,
            "created_at": created_at,
            "updated_at": now,
            "config": _redacted_config(config),
            "artifacts": dict(old.get("artifacts") or {}),
            "warnings": list(old.get("warnings") or [])[-50:],
            "last_error": None,
            "runs": runs,
        }
        _atomic_write(self.manifest_path, payload)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        return payload

    def update_stage(
        self,
        *,
        stage: str,
        title: str = "",
        progress: Optional[float] = None,
    ) -> None:
        payload = self.load()
        if not payload:
            return
        payload["stage"] = stage
        if title:
            payload["stage_title"] = title
        payload["progress"] = progress
        payload["updated_at"] = _now()
        _atomic_write(self.manifest_path, payload)

    def append_log(self, message: str) -> None:
        text = str(message).replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
        if not text:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        stamp = _now()
        with self.log_path.open("a", encoding="utf-8") as handle:
            for line in text.splitlines() or [text]:
                handle.write(f"{stamp} {line}\n")

    def add_warning(self, message: str) -> None:
        payload = self.load()
        if not payload:
            return
        warnings = list(payload.get("warnings") or [])
        warnings.append({"timestamp": _now(), "message": str(message)})
        payload["warnings"] = warnings[-50:]
        payload["updated_at"] = _now()
        _atomic_write(self.manifest_path, payload)

    def finish(
        self,
        *,
        status: str,
        artifacts: Optional[Dict[str, str]] = None,
        error: Optional[str] = None,
    ) -> None:
        payload = self.load()
        if not payload:
            return
        now = _now()
        payload["status"] = status
        payload["stage"] = status
        payload["stage_title"] = status.replace("_", " ").title()
        payload["progress"] = 1.0 if status == "completed" else None
        payload["active_job_id"] = None
        payload["updated_at"] = now
        payload["last_error"] = error
        if artifacts:
            merged = dict(payload.get("artifacts") or {})
            merged.update({str(k): str(v) for k, v in artifacts.items()})
            payload["artifacts"] = merged

        runs = list(payload.get("runs") or [])
        if runs:
            runs[-1] = dict(runs[-1])
            runs[-1]["ended_at"] = now
            runs[-1]["status"] = status
            if error:
                runs[-1]["error"] = error
            payload["runs"] = runs[-20:]
        _atomic_write(self.manifest_path, payload)


def list_projects(output_dir: Path) -> list[dict]:
    root = Path(output_dir).expanduser().resolve() / ".anime_dubber_project" / "projects"
    if not root.exists():
        return []
    rows = []
    for path in root.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        rows.append({
            "project_id": str(data.get("project_id") or path.stem),
            "source": str(data.get("source") or ""),
            "series_id": str(data.get("series_id") or ""),
            "output_dir": str(data.get("output_dir") or Path(output_dir).expanduser()),
            "status": str(data.get("status") or "unknown"),
            "stage": str(data.get("stage") or ""),
            "stage_title": str(data.get("stage_title") or ""),
            "progress": data.get("progress"),
            "updated_at": str(data.get("updated_at") or ""),
            "created_at": str(data.get("created_at") or ""),
            "artifacts": dict(data.get("artifacts") or {}),
            "warning_count": len(data.get("warnings") or []),
            "last_error": data.get("last_error"),
            "manifest_path": str(path),
        })
    known_ids = {str(row.get("project_id") or "") for row in rows}

    # Backfill projects created by v3.x before lightweight manifests existed.
    # This lets the new Projects screen immediately surface existing completed
    # work without forcing users to re-run multi-hour jobs.
    output = Path(output_dir).expanduser().resolve()
    for run_path in output.glob("*_run.json"):
        project_id = run_path.name.removesuffix("_run.json")
        if project_id in known_ids:
            continue
        try:
            metadata = json.loads(run_path.read_text(encoding="utf-8"))
        except Exception:
            metadata = {}
        artifacts: Dict[str, str] = {}
        candidates = {
            "dubbed_video": output / f"{project_id}_EN_DUB.mp4",
            "english_srt": output / f"{project_id}_en.srt",
            "chinese_srt": output / f"{project_id}_zh.srt",
            "character_map": output / f"{project_id}_characters.json",
        }
        for kind, path in candidates.items():
            if path.exists():
                artifacts[kind] = str(path)
        modified = datetime.fromtimestamp(run_path.stat().st_mtime, tz=timezone.utc).isoformat()
        rows.append({
            "project_id": project_id,
            "source": str(metadata.get("source") or ""),
            "series_id": str(metadata.get("series_id") or ""),
            "output_dir": str(output),
            "status": "completed",
            "stage": "completed",
            "stage_title": "Completed",
            "progress": 1.0,
            "updated_at": modified,
            "created_at": modified,
            "artifacts": artifacts,
            "warning_count": 0,
            "last_error": None,
            "manifest_path": "",
            "legacy": True,
        })

    rows.sort(key=lambda row: row.get("updated_at") or "", reverse=True)
    return rows


def get_project(output_dir: Path, project_id: str) -> dict:
    root = Path(output_dir).expanduser().resolve() / ".anime_dubber_project" / "projects"
    path = root / f"{project_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Project not found: {project_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid project manifest: {path}")
    log_path = path.parent.parent / "logs" / f"{project_id}.log"
    data["manifest_path"] = str(path)
    data["log_path"] = str(log_path)
    return data
