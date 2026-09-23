from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple
from urllib.parse import parse_qs, urlparse

WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"
LLM_MODEL = "mlx-community/Qwen3-4B-Instruct-2507-4bit"
DEMUCS_MODEL = "htdemucs"
SAMPLE_RATE = 44100
DIALOGUE_GUARD_PRE = 0.24
DIALOGUE_GUARD_POST = 0.16

DEFAULT_CONTEXT = (
    "Chinese xianxia/xuanhuan cultivation animation. Preserve character names, sect names, realm names, "
    "system terminology, cultivation terminology, and concise dramatic dialogue."
)

DEFAULT_GLOSSARY: Dict[str, str] = {
    "修为": "cultivation",
    "灵根": "spiritual root",
    "境界": "cultivation realm",
    "天劫": "heavenly tribulation",
    "渡劫": "undergo tribulation",
    "宗主": "Sect Master",
    "掌门": "Sect Leader",
    "长老": "Elder",
    "老祖": "Ancestor",
    "丹田": "dantian",
    "元神": "primordial spirit",
    "法宝": "magical treasure",
    "圣地": "sacred land",
    "功法": "cultivation technique",
    "灵气": "spiritual qi",
    "神通": "divine ability",
    "秘境": "secret realm",
    "仙帝": "Immortal Emperor",
    "大帝": "Great Emperor",
    "天骄": "heavenly prodigy",
    "丹药": "spirit pill",
    "系统": "system",
    "天墟圣殿": "Tianxu Holy Temple",
    "胤天绝": "Yin Tianjue",
}


class PipelineError(RuntimeError):
    pass


class CancelledError(PipelineError):
    pass


class ReviewRequired(CancelledError):
    """A dub has finished subtitle review and awaits an explicit decision."""


ProgressCallback = Callable[[str], None]


@dataclass
class Segment:
    start: float
    end: float
    text: str
    translated: str = ""
    speaker_id: str = ""
    style: str = "normal"
    style_confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "start": float(self.start),
            "end": float(self.end),
            "text": self.text,
            "translated": self.translated,
            "speaker_id": self.speaker_id,
            "style": self.style,
            "style_confidence": float(self.style_confidence),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Segment":
        return cls(
            start=float(d["start"]),
            end=float(d["end"]),
            text=str(d.get("text", "")),
            translated=str(d.get("translated", "")),
            speaker_id=str(d.get("speaker_id", "")),
            style=str(d.get("style", "normal")),
            style_confidence=float(d.get("style_confidence", 0.0)),
        )


@dataclass
class Config:
    source: str
    output_dir: Path
    mode: str = "dub"  # subtitles|dub
    target_language: str = "en"
    source_language: str = "zh"
    version_id: str = ""
    asr_provider: str = "auto"  # auto|mlx_whisper|faster_whisper
    faster_whisper_model: str = "large-v3"
    faster_whisper_device: str = "auto"  # auto|cpu|cuda
    faster_whisper_compute_type: str = "auto"
    translation: str = "llm"  # auto|llm|ollama|whisper
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:4b"
    tts_engine: str = "auto"  # auto|chatterbox|kokoro|macos|piper|elevenlabs
    voice: str = ""
    chatterbox_reference_audio: str = ""
    auto_voice_references: bool = True
    chatterbox_expressiveness: float = 0.5
    chatterbox_device: str = "auto"  # auto|mps|cuda|cpu
    chatterbox_turbo: bool = True
    kokoro_voice: str = "auto"
    kokoro_language: str = "a"
    piper_model: str = ""
    piper_speaker: int = -1
    tts_rate: int = 210
    context: str = DEFAULT_CONTEXT
    glossary: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_GLOSSARY))
    keep_work: bool = True
    resume: bool = True
    force: bool = False
    demucs_device: str = "auto"  # auto|mps|cpu
    chunk_seconds: int = 120
    background_volume: float = 1.0
    dub_volume: float = 1.15
    ducking: bool = False
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"
    elevenlabs_model_id: str = "eleven_v3"
    multi_character: bool = True
    max_speakers: int = 12
    speaker_threshold: float = 0.0
    series_id: str = ""
    speaker_backend: str = "auto"  # auto|ecapa|acoustic
    review_before_dub: bool = False
    review_model: str = "mlx-community/Qwen3-8B-4bit"


class CommandRunner:
    def __init__(self, progress: Optional[ProgressCallback] = None):
        self.progress = progress or (lambda _m: None)
        self._lock = threading.Lock()
        self._proc: Optional[subprocess.Popen] = None
        self.cancel_event = threading.Event()
        self.pause_requested = False

    def cancel(self, *, pause: bool = False) -> None:
        self.pause_requested = pause
        self.cancel_event.set()
        with self._lock:
            proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def check_cancel(self) -> None:
        if self.cancel_event.is_set():
            raise CancelledError("Paused by user" if self.pause_requested else "Cancelled by user")

    def run(
        self,
        cmd: Sequence[str],
        *,
        cwd: Optional[Path] = None,
        capture: bool = True,
        check: bool = True,
        env: Optional[dict] = None,
    ) -> subprocess.CompletedProcess:
        self.check_cancel()
        kwargs = {
            "cwd": str(cwd) if cwd else None,
            "env": env,
            "text": True,
            "stdout": subprocess.PIPE if capture else None,
            "stderr": subprocess.PIPE if capture else None,
        }
        proc = subprocess.Popen(list(map(str, cmd)), **kwargs)
        with self._lock:
            self._proc = proc
        try:
            stdout, stderr = proc.communicate()
        finally:
            with self._lock:
                self._proc = None
        if self.cancel_event.is_set():
            raise CancelledError("Paused by user" if self.pause_requested else "Cancelled by user")
        cp = subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
        if check and cp.returncode != 0:
            tail = (stderr or stdout or "")[-4000:]
            raise PipelineError(f"Command failed ({cp.returncode}): {' '.join(map(str, cmd))}\n{tail}")
        return cp


    def run_stream(
        self,
        cmd: Sequence[str],
        *,
        cwd: Optional[Path] = None,
        env: Optional[dict] = None,
        line_callback: Optional[Callable[[str], None]] = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        """Run a command while streaming combined stdout/stderr line-by-line."""
        self.check_cancel()
        proc = subprocess.Popen(
            list(map(str, cmd)),
            cwd=str(cwd) if cwd else None,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
        )
        with self._lock:
            self._proc = proc

        lines: List[str] = []
        try:
            assert proc.stdout is not None
            for raw in iter(proc.stdout.readline, ""):
                if self.cancel_event.is_set():
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    raise CancelledError("Cancelled by user")
                line = raw.rstrip("\r\n")
                lines.append(line)
                if line_callback:
                    line_callback(line)
            proc.stdout.close()
            code = proc.wait()
        finally:
            with self._lock:
                if self._proc is proc:
                    self._proc = None

        stdout = "\n".join(lines)
        if check and code != 0:
            tail = stdout[-4000:]
            raise PipelineError(f"Command failed ({code}): {' '.join(map(str, cmd))}\n{tail}")
        return subprocess.CompletedProcess(list(map(str, cmd)), code, stdout, "")


def sanitize_name(text: str, max_len: int = 80) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text.strip())
    text = re.sub(r"_+", "_", text).strip("._-")
    return (text or "video")[:max_len]


def source_key(source: str) -> str:
    p = Path(source).expanduser()
    if p.exists():
        return sanitize_name(p.stem)
    try:
        u = urlparse(source)
        if u.netloc in {"youtu.be", "www.youtu.be"} and u.path.strip("/"):
            return sanitize_name(u.path.strip("/").split("/")[0])
        if "youtube.com" in u.netloc:
            vid = parse_qs(u.query).get("v", [""])[0]
            if vid:
                return sanitize_name(vid)
    except Exception:
        pass
    return "url_" + hashlib.sha1(source.encode("utf-8")).hexdigest()[:10]


def is_url(source: str) -> bool:
    try:
        return urlparse(source).scheme in {"http", "https"}
    except Exception:
        return False


def srt_timestamp(seconds: float) -> str:
    ms = max(0, int(round(float(seconds) * 1000)))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def write_srt(segments: Sequence[Segment], path: Path, translated: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("w", encoding="utf-8") as f:
            n = 1
            for seg in segments:
                text = seg.translated if translated else seg.text
                text = (text or "").strip()
                if not text:
                    continue
                if not (math.isfinite(float(seg.start)) and math.isfinite(float(seg.end))) or float(seg.end) <= float(seg.start):
                    continue
                f.write(f"{n}\n{srt_timestamp(seg.start)} --> {srt_timestamp(seg.end)}\n{text}\n\n")
                n += 1
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def write_vtt(segments: Sequence[Segment], path: Path, translated: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("w", encoding="utf-8") as handle:
            handle.write("WEBVTT\n\n")
            for seg in segments:
                value = ((seg.translated if translated else seg.text) or "").strip()
                if not value or not (math.isfinite(seg.start) and math.isfinite(seg.end)) or seg.end <= seg.start:
                    continue
                start = srt_timestamp(seg.start).replace(",", ".")
                end = srt_timestamp(seg.end).replace(",", ".")
                handle.write(f"{start} --> {end}\n{value}\n\n")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def _complete_wav(path: Path, *, minimum_seconds: float = 0.01) -> bool:
    """Reject interrupted WAV writes, including files with a valid but short header."""
    try:
        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            expected = frames * handle.getnchannels() * handle.getsampwidth()
            return (frames / handle.getframerate() >= minimum_seconds
                    and path.stat().st_size >= expected + 44)
    except (OSError, EOFError, ValueError, wave.Error, ZeroDivisionError):
        return False


def _atomic_media_run(runner: CommandRunner, cmd: List[str], path: Path) -> None:
    """Publish a stage output only after ffmpeg exits successfully."""
    temp = path.with_name(path.stem + ".partial" + path.suffix)
    temp.unlink(missing_ok=True)
    try:
        runner.run([*cmd[:-1], str(temp)])
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def _atomic_json_write(path: Path, payload: object) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def ffprobe_duration(path: Path, runner: CommandRunner) -> float:
    cp = runner.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)
    ])
    try:
        return float((cp.stdout or "").strip())
    except ValueError as e:
        raise PipelineError(f"Could not determine media duration for {path}") from e


def atempo_chain(factor: float) -> str:
    if factor <= 0:
        raise ValueError("tempo factor must be > 0")
    values: List[float] = []
    while factor > 2.0:
        values.append(2.0)
        factor /= 2.0
    while factor < 0.5:
        values.append(0.5)
        factor /= 0.5
    values.append(factor)
    return ",".join(f"atempo={v:.6f}" for v in values)


def _segment_text_key(text: str) -> str:
    # Collapse punctuation/case differences when detecting impossible duplicate
    # timestamp-token fragments (for example: "pret" / "pret'").
    return re.sub(r"[^\w]+", "", (text or "").casefold(), flags=re.UNICODE)


def sanitize_segments(
    segments: Sequence[Segment],
    *,
    min_duration: float = 0.18,
    duplicate_window: float = 0.40,
) -> List[Segment]:
    """Repair malformed Whisper timestamp segments before they reach SRT/TTS.

    Whisper timestamps are quantized in very small steps and, on difficult long-form
    audio, can occasionally contain reversed ranges or bursts of duplicate micro-
    segments.  The dubbing pipeline must never propagate those raw timestamps into
    TTS.  We preserve the dialogue text where possible, collapse only obviously
    duplicated micro-segments, and guarantee a positive duration.
    """
    cleaned: List[Segment] = []
    minimum = max(0.05, float(min_duration))

    candidates: List[Tuple[int, Segment, float]] = []
    for order, seg in enumerate(segments):
        text = (seg.text or "").strip()
        if not text or not re.search(r"\w", text, flags=re.UNICODE):
            continue
        try:
            start = float(seg.start)
            end = float(seg.end)
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(start) and math.isfinite(end)):
            continue
        start = max(0.0, start)
        raw_duration = end - start
        # Keep the original ordering as a tie-breaker, but repair locally in time order.
        candidates.append((order, Segment(
            start, end, text, seg.translated, seg.speaker_id, seg.style, seg.style_confidence
        ), raw_duration))

    candidates.sort(key=lambda x: (x[1].start, x[0]))

    for _order, cur, raw_duration in candidates:
        key = _segment_text_key(cur.text)
        suspicious = raw_duration < 0.25

        if cleaned:
            prev = cleaned[-1]
            prev_key = _segment_text_key(prev.text)
            near = abs(cur.start - prev.start) <= duplicate_window or cur.start <= prev.end + 0.08
            prev_suspicious = (prev.end - prev.start) < 0.25
            if key and key == prev_key and near and (suspicious or prev_suspicious):
                prev.start = min(prev.start, cur.start)
                prev.end = max(prev.end, cur.end, prev.start + minimum)
                continue

        # Reversed/zero timestamps and physically unusable micro-segments are repaired
        # instead of being allowed to produce zero-sample TTS files.
        if cur.end <= cur.start or (cur.end - cur.start) < minimum:
            cur.end = cur.start + minimum
        cleaned.append(cur)

    return cleaned


def coalesce_segments(segments: Sequence[Segment], max_duration: float = 6.0, max_chars: int = 100) -> List[Segment]:
    out: List[Segment] = []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        cur = Segment(seg.start, seg.end, text)
        if out:
            prev = out[-1]
            gap = cur.start - prev.end
            combined_dur = cur.end - prev.start
            combined_chars = len(prev.text) + len(cur.text)
            if 0 <= gap <= 0.28 and combined_dur <= max_duration and combined_chars <= max_chars:
                prev.end = cur.end
                prev.text = (prev.text.rstrip() + " " + cur.text.lstrip()).strip()
                continue
        out.append(cur)
    return out


def glossary_string(glossary: Dict[str, str]) -> str:
    return "; ".join(f"{k}={v}" for k, v in glossary.items())


def extract_json_array(text: str) -> Optional[list]:
    if not text:
        return None
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end < start:
        return None
    try:
        value = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, list) else None


def parse_translation_response(text: str, expected_ids: Sequence[int]) -> Dict[int, str]:
    parsed: Dict[int, str] = {}
    arr = extract_json_array(text)
    if arr is not None:
        for item in arr:
            if isinstance(item, dict) and "id" in item and "text" in item:
                try:
                    idx = int(item["id"])
                except Exception:
                    continue
                val = str(item["text"]).strip()
                if val:
                    parsed[idx] = val
    if len(parsed) < len(expected_ids):
        for line in text.splitlines():
            m = re.match(r"^\s*(\d+)\s*[|:]\s*(.+?)\s*$", line)
            if m:
                parsed.setdefault(int(m.group(1)), m.group(2).strip())
    return {i: parsed[i] for i in expected_ids if i in parsed and parsed[i]}


def _response_text(response) -> str:
    if isinstance(response, str):
        return response
    txt = getattr(response, "text", None)
    if txt is not None:
        return str(txt)
    return str(response)


def translate_with_llm(
    segments: List[Segment],
    config: Config,
    work_dir: Path,
    runner: CommandRunner,
    progress: ProgressCallback,
) -> List[Segment]:
    target = {"en": "English", "es": "Spanish", "fr": "French", "de": "German", "ja": "Japanese"}[config.target_language]
    signature_inputs = {
        "model": LLM_MODEL,
        "target_language": config.target_language,
        "context": config.context,
        "glossary": config.glossary,
        "source_text": [s.text for s in segments],
    }
    translation_signature = hashlib.sha1(json.dumps(
        signature_inputs, ensure_ascii=False, sort_keys=True
    ).encode("utf-8")).hexdigest()[:12]
    cache_path = work_dir / f"translations_llm_{translation_signature}.json"
    cache: Dict[str, str] = {}
    legacy_path = None
    if config.target_language == "en":
        old_inputs = dict(signature_inputs)
        old_inputs.pop("target_language")
        old_signature = hashlib.sha1(json.dumps(
            old_inputs, ensure_ascii=False, sort_keys=True
        ).encode("utf-8")).hexdigest()[:12]
        legacy_path = work_dir / f"translations_llm_{old_signature}.json"
    if config.resume and not config.force:
        legacy_count = 0
        for candidate in (legacy_path, cache_path):
            if not candidate or not candidate.exists():
                continue
            try:
                loaded = json.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    valid = {str(i): value for i, value in loaded.items()
                             if str(i).isdigit() and int(i) < len(segments)
                             and isinstance(value, str) and bool(value.strip())}
                    cache.update(valid)
                    if candidate == legacy_path:
                        legacy_count = len(valid)
            except (ValueError, OSError):
                continue
        if legacy_count:
            _atomic_json_write(cache_path, cache)
            progress(f"Reused {legacy_count} lines from the earlier English translation cache")

    pending = [i for i, s in enumerate(segments) if str(i) not in cache]
    if not pending:
        for i, seg in enumerate(segments):
            seg.translated = cache.get(str(i), "")
        return segments

    try:
        from mlx_lm import generate, load
    except Exception as e:
        raise PipelineError("mlx-lm is not installed correctly. Re-run setup.sh") from e

    progress(f"Loading translation LLM: {LLM_MODEL}")
    runner.check_cancel()
    model, tokenizer = load(LLM_MODEL)

    def generate_text(prompt: str, max_tokens: int = 2200) -> str:
        messages = [{"role": "user", "content": prompt}]
        if getattr(tokenizer, "chat_template", None) is not None:
            rendered = tokenizer.apply_chat_template(messages, add_generation_prompt=True)
        else:
            rendered = prompt
        response = generate(model, tokenizer, prompt=rendered, max_tokens=max_tokens, verbose=False)
        return _response_text(response)

    batch_size = 12
    gl = glossary_string(config.glossary)
    done = 0
    total = len(pending)
    for off in range(0, len(pending), batch_size):
        runner.check_cancel()
        ids = pending[off:off + batch_size]
        payload = [{"id": i, "text": segments[i].text} for i in ids]
        prompt = (
            f"Translate the following Chinese dialogue into natural concise {target} for an episodic xianxia/cultivation animation.\n"
            "Rules:\n"
            f"1. Return ONLY a JSON array of objects with exactly the same ids, each shaped {{\"id\": number, \"text\": \"{target}\"}}.\n"
            "2. Do not omit, merge, summarize, explain, or add dialogue.\n"
            "3. Keep proper names, sect names, realm names, and terminology consistent.\n"
            f"4. Prefer short spoken {target} so dubbing can fit the original timing.\n"
            f"Context: {config.context}\n"
            f"Glossary: {gl}\n"
            f"Input: {json.dumps(payload, ensure_ascii=False)}"
        )
        parsed: Dict[int, str] = {}
        for attempt in range(3):
            text = generate_text(prompt)
            parsed = parse_translation_response(text, ids)
            if len(parsed) == len(ids):
                break
            prompt += "\nYour previous response was malformed. Return the exact requested JSON array and nothing else."

        missing = [i for i in ids if i not in parsed]
        for i in missing:
            one_prompt = (
                f"Translate this Chinese xianxia dialogue into concise natural {target}. Return ONLY the translation, no quotes or explanation.\n"
                f"Context: {config.context}\nGlossary: {gl}\nChinese: {segments[i].text}"
            )
            raw = generate_text(one_prompt, max_tokens=256).strip()
            raw = re.sub(r"^```.*?\n|\n```$", "", raw, flags=re.S).strip().strip('"')
            if not raw:
                raw = segments[i].text
            parsed[i] = raw.splitlines()[0].strip() if "\n" in raw else raw

        for i in ids:
            cache[str(i)] = parsed.get(i, segments[i].text)
            segments[i].translated = cache[str(i)]
        _atomic_json_write(cache_path, cache)
        done += len(ids)
        progress(f"LLM translation: {min(done, total)}/{total} lines")
    return segments


def translate_with_ollama_provider(
    segments: List[Segment],
    config: Config,
    work_dir: Path,
    runner: CommandRunner,
    progress: ProgressCallback,
) -> List[Segment]:
    target = {"en": "English", "es": "Spanish", "fr": "French", "de": "German", "ja": "Japanese"}[config.target_language]
    from .providers.translation import translate_with_ollama

    translation_signature = hashlib.sha1(json.dumps({
        "provider": "ollama",
        "target_language": config.target_language,
        "model": config.ollama_model,
        "url": config.ollama_url,
        "context": config.context,
        "glossary": config.glossary,
        "source_text": [s.text for s in segments],
    }, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    cache_path = work_dir / f"translations_ollama_{translation_signature}.json"
    cache: Dict[str, str] = {}
    if config.resume and cache_path.exists() and not config.force:
        try:
            loaded = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                cache = {str(i): value for i, value in loaded.items()
                         if str(i).isdigit() and int(i) < len(segments)
                         and isinstance(value, str) and bool(value.strip())}
        except Exception:
            cache = {}

    pending = [i for i, seg in enumerate(segments) if str(i) not in cache]
    if not pending:
        for i, seg in enumerate(segments):
            seg.translated = cache.get(str(i), "")
        return segments

    progress(f"Using Ollama translation model: {config.ollama_model}")
    gl = glossary_string(config.glossary)
    batch_size = 12
    batches = []
    for off in range(0, len(pending), batch_size):
        ids = pending[off:off + batch_size]
        payload = [{"id": i, "text": segments[i].text} for i in ids]
        prompt = (
            f"Translate the following Chinese dialogue into natural concise {target} for an episodic "
            "xianxia/cultivation animation.\n"
            "Rules:\n"
            "1. Return ONLY a JSON array of objects with exactly the same ids, each shaped "
            f"{{\"id\": number, \"text\": \"{target}\"}}.\n"
            "2. Do not omit, merge, summarize, explain, or add dialogue.\n"
            "3. Keep proper names, sect names, realm names, and terminology consistent.\n"
            f"4. Prefer short spoken {target} so dubbing can fit the original timing.\n"
            f"Context: {config.context}\n"
            f"Glossary: {gl}\n"
            f"Input: {json.dumps(payload, ensure_ascii=False)}"
        )
        batches.append((ids, prompt))

    def single_prompt(idx: int) -> str:
        return (
            f"Translate this Chinese xianxia dialogue into concise natural {target}. "
            "Return ONLY the translation, no quotes or explanation.\n"
            f"Context: {config.context}\n"
            f"Glossary: {gl}\n"
            f"Chinese: {segments[idx].text}"
        )

    def save_batch(ids: List[int], values: Dict[int, str]) -> None:
        for idx in ids:
            cache[str(idx)] = values.get(idx) or segments[idx].text
        _atomic_json_write(cache_path, cache)

    try:
        translated = translate_with_ollama(
            batches=batches,
            base_url=config.ollama_url,
            model=config.ollama_model,
            parse_batch=parse_translation_response,
            single_prompt=single_prompt,
            cancel_check=runner.check_cancel,
            progress=progress,
            on_batch=save_batch,
        )
    except Exception as e:
        raise PipelineError(str(e)) from e

    for idx in pending:
        value = translated.get(idx) or segments[idx].text
        cache[str(idx)] = value
        segments[idx].translated = value
    _atomic_json_write(cache_path, cache)
    return segments


def _precise_row_bounds(row: dict) -> Tuple[float, float]:
    """Prefer first/last word timestamps when Whisper supplies them."""
    start = float(row.get("start", 0.0) or 0.0)
    end = float(row.get("end", 0.0) or 0.0)
    words = row.get("words") or []

    valid = []
    for word in words:
        try:
            if isinstance(word, dict):
                ws = float(word.get("start", 0.0) or 0.0)
                we = float(word.get("end", 0.0) or 0.0)
            else:
                ws = float(getattr(word, "start", 0.0) or 0.0)
                we = float(getattr(word, "end", 0.0) or 0.0)
        except Exception:
            continue
        if math.isfinite(ws) and math.isfinite(we) and we > ws:
            valid.append((ws, we))

    if valid:
        word_start = valid[0][0]
        word_end = valid[-1][1]
        if word_start >= max(0.0, start - 0.75) and word_start <= end + 0.25:
            start = word_start
        if word_end >= start and word_end <= end + 0.75:
            end = word_end

    return start, end


def transcribe_audio(
    audio: Path,
    config: Config,
    work_dir: Path,
    runner: CommandRunner,
    progress: ProgressCallback,
    *,
    task: str = "transcribe",
) -> List[Segment]:
    from .providers.asr import resolve_asr_provider

    provider = resolve_asr_provider(config.asr_provider)
    cache_name = (
        f"transcript_zh_{provider}_v5_precise.json"
        if task == "transcribe"
        else f"transcript_en_{provider}_v5_precise.json"
    )
    if provider == "faster_whisper" and config.faster_whisper_model != "large-v3":
        model_tag = hashlib.sha1(config.faster_whisper_model.encode("utf-8")).hexdigest()[:8]
        cache_name = cache_name.replace("_v5_precise", f"_{model_tag}_v5_precise")
    cache = work_dir / cache_name
    legacy_cache = work_dir / (
        "transcript_zh_v3.json" if task == "transcribe" else "transcript_en_whisper_v3.json"
    )
    previous_v4 = work_dir / (
        f"transcript_zh_{provider}_v4.json"
        if task == "transcribe"
        else f"transcript_en_{provider}_v4.json"
    )
    cache_to_read = cache
    if (
        config.resume
        and not config.force
        and not cache.exists()
        and (previous_v4.exists() or legacy_cache.exists())
    ):
        progress(
            "Precise lip-sync timing upgrade: rebuilding Whisper timestamps once "
            "with word-level timing; compatible translation/cache data will still be reused."
        )

    if config.resume and cache_to_read.exists() and not config.force:
        try:
            data = json.loads(cache_to_read.read_text(encoding="utf-8"))
            if not isinstance(data, list) or not data:
                raise ValueError("Empty transcript cache")
            raw_cached = [Segment.from_dict(x) for x in data]
            cleaned = sanitize_segments(raw_cached)
            if not cleaned:
                raise ValueError("No usable transcript segments")
            if len(cleaned) != len(raw_cached) or any(
                abs(a.start - b.start) > 1e-6 or abs(a.end - b.end) > 1e-6 or a.text != b.text
                for a, b in zip(cleaned, raw_cached)
            ):
                progress(f"Repaired cached transcript timing: {len(raw_cached)} -> {len(cleaned)} segments")
                _atomic_json_write(cache, [seg.to_dict() for seg in cleaned])
            return cleaned
        except (ValueError, TypeError, KeyError, OSError):
            progress("Transcript cache was incomplete; rebuilding this stage…")
    initial_prompt = (
        "玄幻 修仙 系统 天墟圣殿 胤天绝 修为 灵根 境界 宗主 掌门 长老 老祖 天劫 丹田 元神 法宝"
        if task == "transcribe" else None
    )
    runner.check_cancel()

    if provider == "mlx_whisper":
        try:
            import mlx_whisper
        except Exception as e:
            raise PipelineError(
                "MLX Whisper was selected but mlx-whisper is not installed. "
                "On Windows/Linux install faster-whisper and use --asr faster-whisper."
            ) from e
        progress(
            "Transcribing Mandarin with MLX-Whisper…"
            if task == "transcribe"
            else "Translating speech directly with MLX-Whisper…"
        )
        result = mlx_whisper.transcribe(
            str(audio),
            path_or_hf_repo=WHISPER_MODEL,
            language="zh",
            task=task,
            initial_prompt=initial_prompt,
            word_timestamps=True,
        )
        provider_rows = result.get("segments", [])
    elif provider == "faster_whisper":
        from .providers.asr import faster_whisper_segments
        progress(
            f"Transcribing Mandarin with Faster-Whisper ({config.faster_whisper_model})…"
            if task == "transcribe"
            else f"Translating speech directly with Faster-Whisper ({config.faster_whisper_model})…"
        )
        try:
            provider_rows = faster_whisper_segments(
                audio,
                task=task,
                model_name=config.faster_whisper_model,
                device=config.faster_whisper_device,
                compute_type=config.faster_whisper_compute_type,
                language="zh",
                initial_prompt=initial_prompt,
                cancel_check=runner.check_cancel,
            )
        except Exception as e:
            raise PipelineError(str(e)) from e
    else:
        raise PipelineError(f"Unsupported ASR provider: {provider}")

    raw_segs = []
    for x in provider_rows:
        text = str(x.get("text", "")).strip()
        if not text:
            continue
        precise_start, precise_end = _precise_row_bounds(x)
        raw_segs.append(Segment(precise_start, precise_end, text))
    segs = sanitize_segments(raw_segs)
    if len(segs) != len(raw_segs) or any(
        abs(a.start - b.start) > 1e-6 or abs(a.end - b.end) > 1e-6 or a.text != b.text
        for a, b in zip(segs, raw_segs)
    ):
        progress(f"Repaired Whisper transcript timing: {len(raw_segs)} -> {len(segs)} segments")
    # Preserve Whisper boundaries for multi-character analysis. Coalescing adjacent
    # lines can accidentally merge two different speakers.
    if not config.multi_character:
        segs = coalesce_segments(segs)
    _atomic_json_write(cache, [s.to_dict() for s in segs])
    return segs


def _yt_dlp_base() -> list[str]:
    """Always use the yt-dlp installed in this app's virtual environment.

    Using a bare `yt-dlp` executable can accidentally pick up an old user-level
    install earlier on PATH, which is exactly the kind of mismatch that causes
    confusing YouTube 403/SABR failures.
    """
    return [sys.executable, "-m", "yt_dlp"]


def _locate_downloaded_source(work_dir: Path, stdout: str = "") -> Optional[Path]:
    candidates = [Path(x.strip()) for x in (stdout or "").splitlines() if x.strip()]
    for p in reversed(candidates):
        if p.is_file() and p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}:
            return p
    fallback = sorted(work_dir.glob("source.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in fallback:
        if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"} and p.name.count(".") == 1:
            return p
    return None


def download_source(source: str, work_dir: Path, runner: CommandRunner, progress: ProgressCallback) -> Path:
    if not is_url(source):
        p = Path(source).expanduser().resolve()
        if not p.exists():
            raise PipelineError(f"Input file does not exist: {p}")
        return p

    cached = [p for p in work_dir.glob("source.*")
              if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"} and p.name.count(".") == 1]
    if cached:
        chosen = max(cached, key=lambda p: p.stat().st_mtime)
        try:
            if ffprobe_duration(chosen, runner) > 0:
                progress(f"Using cached source video: {chosen.name}")
                return chosen
        except PipelineError:
            progress("Cached source video was incomplete; resuming download…")

    target = work_dir / "source.%(ext)s"
    common = [
        *_yt_dlp_base(),
        "--no-playlist",
        "--restrict-filenames",
        "--force-ipv4",
        "--merge-output-format", "mp4",
        "--print", "after_move:filepath",
        "-o", str(target),
    ]

    # YouTube has been changing delivery behavior (SABR/PO-token/client rules).
    # Try several official yt-dlp-compatible paths instead of failing on the
    # first progressive HTTPS format that returns 403.
    attempts = [
        (
            "standard 1080p",
            [
                "-f", "bv*[height<=1080]+ba/b[height<=1080]/b",
            ],
        ),
        (
            "web-embedded client",
            [
                "--extractor-args", "youtube:player_client=web_embedded",
                "-f", "bv*[height<=1080]+ba/b[height<=1080]/b",
            ],
        ),
        (
            "web-embedded HLS fallback",
            [
                "--extractor-args", "youtube:player_client=web_embedded",
                "-f", "96/95/94/93/92/91/b[protocol^=m3u8][height<=1080]/18/b[height<=1080]/b",
            ],
        ),
    ]

    errors: list[str] = []
    for idx, (label, extra) in enumerate(attempts, 1):
        # Remove remnants from a failed attempt so a .part file cannot be mistaken
        # for a valid cached source on the next try.
        for stale in work_dir.glob("source.*"):
            if stale.suffix.lower() in {".part", ".ytdl"}:
                try:
                    stale.unlink()
                except OSError:
                    pass

        progress(f"Downloading source video with yt-dlp ({label}, attempt {idx}/{len(attempts)})…")
        try:
            command = [
                *common,
                "--newline",
                "--progress",
                "--progress-template",
                "download:__YTDLP_PROGRESS__|%(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s|%(progress._total_bytes_str)s",
                "--print",
                "after_move:__YTDLP_FILE__:%(filepath)s",
                *extra,
                source,
            ]

            def on_line(line: str) -> None:
                if line.startswith("__YTDLP_PROGRESS__|"):
                    parts = line.split("|", 4)
                    pct_raw = parts[1].strip().replace("%", "") if len(parts) > 1 else ""
                    speed = parts[2].strip() if len(parts) > 2 else ""
                    eta = parts[3].strip() if len(parts) > 3 else ""
                    total = parts[4].strip() if len(parts) > 4 else ""
                    try:
                        pct = max(0.0, min(100.0, float(pct_raw)))
                    except ValueError:
                        pct = 0.0
                    progress(f"__DOWNLOAD_PROGRESS__|{pct:.2f}|{speed}|{eta}|{total}|{idx}|{len(attempts)}")
                elif line and not line.startswith("__YTDLP_FILE__:"):
                    lower = line.lower()
                    if "warning:" in lower or "error:" in lower:
                        progress(line)

            cp = runner.run_stream(command, line_callback=on_line)
            file_lines = []
            for line in (cp.stdout or "").splitlines():
                if line.startswith("__YTDLP_FILE__:"):
                    file_lines.append(line.split(":", 1)[1].strip())
            found = _locate_downloaded_source(work_dir, "\n".join(file_lines))
            if found:
                progress(f"__DOWNLOAD_PROGRESS__|100.00|done|0|complete|{idx}|{len(attempts)}")
                return found
            errors.append(f"{label}: yt-dlp exited successfully but no output file was found")
        except Exception as exc:
            errors.append(f"{label}: {exc}")

    details = "\n\n".join(errors[-3:])
    raise PipelineError(
        "YouTube download failed after automatic fallbacks.\n\n"
        "The app used its bundled/current yt-dlp, forced IPv4, then retried with "
        "the web-embedded client and HLS formats. YouTube may be requiring a "
        "logged-in browser session or may have changed its delivery rules again.\n\n"
        f"Attempt details:\n{details}"
    )


def extract_audio(video: Path, work_dir: Path, runner: CommandRunner, progress: ProgressCallback, config: Config) -> Path:
    audio = work_dir / "original.wav"
    if config.resume and _complete_wav(audio) and not config.force:
        return audio
    progress("Extracting original soundtrack…")
    _atomic_media_run(runner, [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(video), "-vn", "-ac", "2", "-ar", str(SAMPLE_RATE),
        "-c:a", "pcm_s16le", str(audio)
    ], audio)
    return audio


def _find_stem(stems_dir: Path, name: str) -> Optional[Path]:
    files = [p for p in stems_dir.rglob(name) if _complete_wav(p)]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_size)


def separate_dialogue(
    audio: Path,
    work_dir: Path,
    runner: CommandRunner,
    progress: ProgressCallback,
    config: Config,
) -> Tuple[Path, Path]:
    stems_dir = work_dir / "stems"
    vocals = _find_stem(stems_dir, "vocals.wav")
    bg = _find_stem(stems_dir, "no_vocals.wav")
    audio_seconds = ffprobe_duration(audio, runner)
    if (config.resume and vocals and bg and not config.force
            and _complete_wav(vocals, minimum_seconds=audio_seconds * .98)
            and _complete_wav(bg, minimum_seconds=audio_seconds * .98)):
        return vocals, bg
    # Demucs writes directly to final paths. A stopped run can leave a valid
    # short WAV with a repaired header; remove both stems before retrying.
    if vocals or bg:
        for old in stems_dir.rglob("vocals.wav"):
            old.unlink(missing_ok=True)
        for old in stems_dir.rglob("no_vocals.wav"):
            old.unlink(missing_ok=True)
    stems_dir.mkdir(parents=True, exist_ok=True)

    devices: List[str]
    if config.demucs_device == "auto":
        if platform.system() == "Darwin":
            devices = ["mps", "cpu"]
        else:
            devices = ["cpu"]
            try:
                import torch
                if torch.cuda.is_available():
                    devices = ["cuda", "cpu"]
            except Exception:
                pass
    else:
        devices = [config.demucs_device]

    last_error = None
    for device in devices:
        progress(f"Separating dialogue from music/SFX with Demucs ({device})…")
        cmd = [
            sys.executable, "-m", "demucs.separate",
            "--two-stems", "vocals",
            "-n", DEMUCS_MODEL,
            "--device", device,
            "-o", str(stems_dir),
            str(audio),
        ]
        cp = runner.run(cmd, capture=True, check=False)
        if cp.returncode == 0:
            vocals = _find_stem(stems_dir, "vocals.wav")
            bg = _find_stem(stems_dir, "no_vocals.wav")
            if vocals and bg:
                return vocals, bg
        last_error = (cp.stderr or cp.stdout or "")[-3000:]
        if device != devices[-1]:
            progress(f"Demucs {device} failed; retrying on {devices[-1]} for compatibility…")
    raise PipelineError(f"Demucs could not separate the soundtrack.\n{last_error or ''}")


def list_macos_voices(runner: Optional[CommandRunner] = None) -> List[str]:
    if platform.system() != "Darwin" or not shutil.which("say"):
        return []
    try:
        cp = (runner or CommandRunner()).run(["say", "-v", "?"], capture=True)
    except Exception:
        return []
    voices: List[str] = []
    for line in (cp.stdout or "").splitlines():
        m = re.match(r"^(.+?)\s{2,}([a-z]{2}_[A-Z]{2})\s+#", line)
        if m and m.group(2).startswith("en_"):
            voices.append(m.group(1).strip())
    # Keep order, remove dupes. English-only prevents accidental non-English TTS assignment.
    return list(dict.fromkeys(voices))


def synthesize_macos(
    text: str,
    out_aiff: Path,
    config: Config,
    runner: CommandRunner,
    *,
    voice: str = "",
    rate: Optional[int] = None,
) -> None:
    if platform.system() != "Darwin" or not shutil.which("say"):
        raise PipelineError("Local TTS requires the macOS 'say' command")
    txt = out_aiff.with_suffix(".txt")
    txt.write_text(text, encoding="utf-8")
    chosen_rate = int(rate if rate is not None else config.tts_rate)
    chosen_voice = (voice or config.voice).strip()
    cmd = ["say", "-r", str(chosen_rate)]
    if chosen_voice:
        cmd += ["-v", chosen_voice]
    cmd += ["-f", str(txt), "-o", str(out_aiff)]
    try:
        runner.run(cmd)
    finally:
        try:
            txt.unlink()
        except FileNotFoundError:
            pass


def synthesize_elevenlabs(
    text: str,
    out_mp3: Path,
    config: Config,
    runner: CommandRunner,
) -> None:
    key = config.elevenlabs_api_key.strip() or os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise PipelineError("ElevenLabs selected but no API key was supplied. Set ELEVENLABS_API_KEY or enter it in the GUI.")
    if not config.elevenlabs_voice_id.strip():
        raise PipelineError("ElevenLabs requires a voice ID")
    url = (
        "https://api.elevenlabs.io/v1/text-to-speech/"
        + config.elevenlabs_voice_id.strip()
        + "?output_format=mp3_44100_128"
    )
    payload = json.dumps({
        "text": text,
        "model_id": config.elevenlabs_model_id,
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "xi-api-key": key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )
    last_error = None
    for attempt in range(5):
        runner.check_cancel()
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                out_mp3.write_bytes(resp.read())
            return
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[-1200:]
            last_error = f"HTTP {e.code}: {body}"
            if e.code == 429 and attempt < 4:
                time.sleep(2 ** attempt)
                continue
            raise PipelineError(f"ElevenLabs request failed: {last_error}") from e
        except Exception as e:
            last_error = str(e)
            if attempt < 4:
                time.sleep(2 ** attempt)
                continue
            raise PipelineError(f"ElevenLabs request failed: {last_error}") from e


def _pitch_filters(semitones: float) -> List[str]:
    if abs(semitones) < 0.05:
        return []
    factor = 2.0 ** (float(semitones) / 12.0)
    # asetrate changes pitch+tempo; atempo restores the original duration while preserving pitch shift.
    return [f"asetrate={SAMPLE_RATE * factor:.4f}", f"aresample={SAMPLE_RATE}", atempo_chain(1.0 / factor)]


def _chatterbox_reference(profile: dict, config: Config) -> str:
    manual = str(profile.get("reference_audio") or "").strip()
    if manual:
        return manual
    if config.auto_voice_references and profile.get("auto_reference_enabled", True):
        suggested = str(profile.get("suggested_reference_audio") or "").strip()
        if suggested:
            return suggested
    # A project-wide prompt must never override individual characters or
    # quietly turn every character without a clean source clip into its voice.
    return str(config.chatterbox_reference_audio or "").strip() if not profile else ""


def _character_voice_fallback() -> str:
    """Choose a character-specific preset when there is no cloneable prompt."""
    from .providers.tts import kokoro_available
    if kokoro_available():
        return "kokoro"
    if platform.system() == "Darwin" and shutil.which("say"):
        return "macos"
    raise PipelineError(
        "No clean source voice clip was found for a character. Select a reference "
        "in Characters, or install Kokoro to use a voice chosen for that character."
    )


def prepare_tts_clip(
    seg: Segment,
    index: int,
    tts_dir: Path,
    config: Config,
    runner: CommandRunner,
    progress: ProgressCallback,
    profile: Optional[dict] = None,
) -> Path:
    text = (seg.translated or seg.text).strip()
    if not text:
        raise PipelineError(f"Empty translated text for segment {index}")
    profile = profile or {}
    chosen_voice = str(profile.get("macos_voice", "") or config.voice).strip()
    base_rate = int(profile.get("tts_rate", config.tts_rate))
    pitch = float(profile.get("pitch_semitones", 0.0))
    gain = float(profile.get("voice_gain", 1.0))
    style = seg.style or "normal"
    if style == "shouting":
        base_rate = int(base_rate * 1.05)
        pitch += 0.7
        gain *= 1.30
    elif style == "whispering":
        base_rate = int(base_rate * 0.92)
        pitch -= 0.25
        gain *= 0.64

    eleven_voice = str(profile.get("elevenlabs_voice_id", "") or config.elevenlabs_voice_id)
    chatterbox_reference = _chatterbox_reference(profile, config)
    chatterbox_expressiveness = float(
        profile.get("expressiveness", config.chatterbox_expressiveness)
    )
    if style == "shouting":
        chatterbox_expressiveness = min(1.5, chatterbox_expressiveness + 0.25)
    elif style == "whispering":
        chatterbox_expressiveness = max(0.0, chatterbox_expressiveness - 0.15)
    kokoro_voice = str(profile.get("kokoro_voice", "") or config.kokoro_voice).strip()
    profile_engine = str(profile.get("tts_provider", "") or "").strip().lower()
    resolved_tts = profile_engine if profile_engine and profile_engine != "inherit" else config.tts_engine
    if config.target_language != "en" and resolved_tts != "elevenlabs":
        raise PipelineError(
            f"Character {seg.speaker_id or index} uses {resolved_tts}, but non-English dubbing "
            "currently requires an ElevenLabs multilingual voice. Update the character voice override."
        )

    if resolved_tts == "auto":
        from .providers.tts import chatterbox_available, kokoro_available, piper_available

        if chatterbox_available():
            resolved_tts = "chatterbox"
        elif kokoro_available():
            resolved_tts = "kokoro"
        elif platform.system() == "Darwin" and shutil.which("say"):
            resolved_tts = "macos"
        else:
            has_piper_model = bool(config.piper_model.strip() or os.getenv("PIPER_MODEL", "").strip())
            has_elevenlabs_key = bool(
                config.elevenlabs_api_key.strip() or os.getenv("ELEVENLABS_API_KEY", "").strip()
            )
            if piper_available() and (has_piper_model or not has_elevenlabs_key):
                resolved_tts = "piper"
            else:
                resolved_tts = "elevenlabs"

    if resolved_tts == "chatterbox" and config.multi_character and profile and not chatterbox_reference:
        resolved_tts = _character_voice_fallback()
        progress(f"No source voice reference for {seg.speaker_id}; using {resolved_tts} character voice")

    if resolved_tts == "kokoro" and (not kokoro_voice or kokoro_voice == "auto"):
        from .providers.tts import automatic_kokoro_voice
        kokoro_voice = automatic_kokoro_voice(profile)

    signature_data = {
        "processing_version": 2,
        "text": text,
        "engine": resolved_tts,
        "configured_engine": config.tts_engine,
        "profile_engine": profile_engine,
        "voice": chosen_voice,
        "rate": base_rate,
        "pitch": round(pitch, 3),
        "gain": round(gain, 3),
        "style": style,
        "speaker": seg.speaker_id,
        "eleven_voice": eleven_voice,
        "eleven_model": config.elevenlabs_model_id,
        "timing": [round(seg.start, 3), round(seg.end, 3)],
    }
    if resolved_tts == "piper":
        signature_data["piper_model"] = config.piper_model or os.getenv("PIPER_MODEL", "")
        signature_data["piper_speaker"] = config.piper_speaker
    elif resolved_tts == "chatterbox":
        signature_data["reference_audio"] = chatterbox_reference
        if chatterbox_reference:
            ref_path = Path(chatterbox_reference).expanduser()
            if ref_path.is_file():
                signature_data["reference_fingerprint"] = [ref_path.stat().st_size, ref_path.stat().st_mtime_ns]
        signature_data["expressiveness"] = round(chatterbox_expressiveness, 3)
        signature_data["device"] = config.chatterbox_device
        signature_data["turbo"] = bool(config.chatterbox_turbo)
    elif resolved_tts == "kokoro":
        signature_data["kokoro_voice"] = kokoro_voice
        signature_data["kokoro_language"] = config.kokoro_language

    clip_signature = hashlib.sha1(
        json.dumps(signature_data, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    # Local engines emit WAV. Keep the raw and filtered files distinct: ffmpeg
    # cannot write to its own input, and a failed render must never look cached.
    wav = tts_dir / f"{index:06d}_{clip_signature}_processed.wav"
    if config.resume and _complete_wav(wav) and not config.force:
        runner.reused_voice_clips = getattr(runner, "reused_voice_clips", 0) + 1
        return wav
    tts_dir.mkdir(parents=True, exist_ok=True)

    suffix = ".aiff" if resolved_tts == "macos" else (".mp3" if resolved_tts == "elevenlabs" else ".wav")
    source_audio = tts_dir / f"{index:06d}_{clip_signature}{suffix}"
    raw_audio = source_audio
    rendering = tts_dir / f"{index:06d}_{clip_signature}_rendering.wav"
    speech_audio = tts_dir / f"{index:06d}_{clip_signature}_speech.wav"

    if config.resume and source_audio.is_file() and source_audio.stat().st_size > 1000 and not config.force:
        try:
            valid_source = ffprobe_duration(source_audio, runner) > 0.05
        except PipelineError:
            valid_source = False
    else:
        valid_source = False

    if valid_source:
        progress(f"Reusing generated voice for line {index + 1}")
    elif resolved_tts == "chatterbox":
        from .providers.tts import synthesize_chatterbox
        try:
            synthesize_chatterbox(
                text,
                source_audio,
                reference_audio=chatterbox_reference,
                expressiveness=chatterbox_expressiveness,
                device=config.chatterbox_device,
                turbo=bool(config.chatterbox_turbo),
                cancel_check=runner.check_cancel,
            )
        except Exception as e:
            raise PipelineError(str(e)) from e
    elif resolved_tts == "kokoro":
        from .providers.tts import synthesize_kokoro
        try:
            synthesize_kokoro(
                text,
                source_audio,
                voice=kokoro_voice,
                rate=base_rate,
                lang_code=config.kokoro_language,
                cancel_check=runner.check_cancel,
            )
        except Exception as e:
            raise PipelineError(str(e)) from e
    elif resolved_tts == "macos":
        synthesize_macos(text, source_audio, config, runner, voice=chosen_voice, rate=base_rate)
    elif resolved_tts == "piper":
        from .providers.tts import synthesize_piper
        try:
            synthesize_piper(
                text,
                source_audio,
                model_path=config.piper_model,
                rate=base_rate,
                speaker=(config.piper_speaker if config.piper_speaker >= 0 else None),
                cancel_check=runner.check_cancel,
            )
        except Exception as e:
            raise PipelineError(str(e)) from e
    elif resolved_tts == "elevenlabs":
        old = config.elevenlabs_voice_id
        config.elevenlabs_voice_id = eleven_voice
        try:
            synthesize_elevenlabs(text, source_audio, config, runner)
        finally:
            config.elevenlabs_voice_id = old
    else:
        raise PipelineError(f"Unsupported TTS engine: {resolved_tts}")

    # TTS can leave a long silent tail. Timing against the whole file can
    # make even a short utterance appear to need several times playback speed.
    runner.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source_audio),
        "-af", "silenceremove=start_periods=1:start_silence=0.005:start_threshold=-55dB,"
               "areverse,silenceremove=start_periods=1:start_silence=0.08:"
               "start_threshold=-55dB,areverse",
        "-ac", "2", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(speech_audio),
    ])
    try:
        source_dur = ffprobe_duration(speech_audio, runner)
    except PipelineError:
        source_dur = 0.0
    if source_dur <= 0.005:
        progress(f"Warning: silence trimming removed line {index + 1}; using original voice audio")
        speech_audio.unlink(missing_ok=True)
        source_dur = max(0.05, ffprobe_duration(source_audio, runner))
    else:
        source_audio = speech_audio
    target_dur = max(0.18, seg.end - seg.start)
    filters: List[str] = [
        # macOS say and some hosted TTS voices can include a short lead-in.
        # Remove it so the English line starts at the subtitle boundary instead
        # of exposing a faint residual source-language voice first.
        "silenceremove=start_periods=1:start_silence=0.005:start_threshold=-55dB",
        "afade=t=in:st=0:d=0.012",
    ]
    filters.extend(_pitch_filters(pitch))
    if source_dur > target_dur * 1.02:
        factor = source_dur / target_dur
        if factor > 1.5:
            progress(f"Warning: line {index + 1} needs {factor:.1f}× speech compression; "
                     "capping at 1.5× and truncating speech beyond the cue. Shorten this subtitle for a complete line.")
        filters.append(atempo_chain(min(factor, 1.5)))
    if style == "shouting":
        filters += ["acompressor=threshold=0.125:ratio=3:attack=5:release=90"]
    elif style == "whispering":
        filters += ["highpass=f=120", "lowpass=f=6500"]
    filters += [
        f"atrim=duration={target_dur:.6f}",
        f"volume={max(0.1, min(3.0, gain)):.4f}",
        f"aresample={SAMPLE_RATE}",
        "aformat=sample_fmts=s16:channel_layouts=stereo",
    ]
    try:
        runner.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(source_audio),
            "-af", ",".join(filters),
            "-ac", "2", "-ar", str(SAMPLE_RATE),
            "-c:a", "pcm_s16le", str(rendering),
        ])

        # Very short segments can yield an empty WAV after aggressive filters.
        # Retry from the untouched source before publishing the clip to cache.
        try:
            rendered_dur = ffprobe_duration(rendering, runner)
            if rendered_dur <= 0.005:
                raise PipelineError(f"TTS rendered zero-duration audio for segment {index}")
        except PipelineError:
            progress(f"Warning: line {index + 1} produced empty filtered audio; retrying without timing compression")
            safe_filters = [
                "silenceremove=start_periods=1:start_silence=0.005:start_threshold=-55dB",
                "afade=t=in:st=0:d=0.012",
                f"atrim=duration={target_dur:.6f}",
                f"volume={max(0.1, min(3.0, gain)):.4f}",
                f"aresample={SAMPLE_RATE}",
                "aformat=sample_fmts=s16:channel_layouts=stereo",
            ]
            runner.run([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(source_audio),
                "-af", ",".join(safe_filters),
                "-ac", "2", "-ar", str(SAMPLE_RATE),
                "-c:a", "pcm_s16le", str(rendering),
            ])
            rendered_dur = ffprobe_duration(rendering, runner)
            if rendered_dur <= 0.005:
                raise PipelineError(f"TTS produced no audio for segment {index}: {text!r}")
        rendering.replace(wav)
    finally:
        rendering.unlink(missing_ok=True)
        speech_audio.unlink(missing_ok=True)

    raw_audio.unlink(missing_ok=True)
    return wav

def _clips_overlapping(
    clip_infos: Sequence[Tuple[Segment, Path, float]],
    chunk_start: float,
    chunk_end: float,
) -> List[Tuple[Segment, Path, float]]:
    return [x for x in clip_infos if x[0].start < chunk_end and (x[0].start + x[2]) > chunk_start]


def _ffconcat_quote(path: Path) -> str:
    """Quote a file path for ffmpeg's concat demuxer.

    ffconcat uses shell-like single-quoted strings. Apostrophes are represented
    by ending the quote, escaping the apostrophe, and reopening the quote.
    """
    text = path.as_posix()
    return "'" + text.replace("'", "'\\''") + "'"


def render_dub_timeline(
    segments: Sequence[Segment],
    clips: Sequence[Path],
    total_duration: float,
    work_dir: Path,
    config: Config,
    runner: CommandRunner,
    progress: ProgressCallback,
) -> Path:
    timeline_signature = hashlib.sha1(json.dumps({
        "segments": [[round(s.start, 3), round(s.end, 3), str(p)] for s, p in zip(segments, clips)],
        "duration": round(total_duration, 3),
        "chunk_seconds": int(config.chunk_seconds),
    }, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    timeline = work_dir / f"dub_timeline_{timeline_signature}.wav"
    if config.resume and _complete_wav(timeline, minimum_seconds=total_duration * .98) and not config.force:
        return timeline

    progress(f"Checking voice clips: 0/{len(clips)}")
    durations = []
    for idx, clip in enumerate(clips, start=1):
        runner.check_cancel()
        durations.append(ffprobe_duration(clip, runner))
        if idx % 50 == 0 or idx == len(clips):
            progress(f"Checking voice clips: {idx}/{len(clips)}")
    clip_infos = list(zip(segments, clips, durations))
    chunk_dir = work_dir / f"timeline_chunks_{timeline_signature}"
    if chunk_dir.exists() and config.force:
        shutil.rmtree(chunk_dir)
    chunk_dir.mkdir(parents=True, exist_ok=True)

    chunk_seconds = max(30, int(config.chunk_seconds))
    chunks: List[Path] = []
    count = max(1, int(math.ceil(total_duration / chunk_seconds)))
    progress(f"Rendering dub timeline: 0/{count}")
    for n in range(count):
        runner.check_cancel()
        start = n * chunk_seconds
        end = min(total_duration, (n + 1) * chunk_seconds)
        dur = max(0.01, end - start)
        out = chunk_dir / f"chunk_{n:05d}.wav"
        chunks.append(out)
        if config.resume and _complete_wav(out, minimum_seconds=dur * .98) and not config.force:
            progress(f"Rendering dub timeline: {n + 1}/{count} (cached)")
            continue
        overlaps = _clips_overlapping(clip_infos, start, end)
        cmd: List[str] = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-t", f"{dur:.6f}", "-i", f"anullsrc=r={SAMPLE_RATE}:cl=stereo",
        ]
        for _seg, path, _clip_dur in overlaps:
            cmd += ["-i", str(path)]

        filters: List[str] = ["[0:a]asetpts=PTS-STARTPTS[base]"]
        mix_labels = ["[base]"]
        for j, (seg, _path, clip_dur) in enumerate(overlaps, start=1):
            clip_abs_start = seg.start
            clip_abs_end = seg.start + clip_dur
            slice_start = max(0.0, start - clip_abs_start)
            slice_end = min(clip_dur, end - clip_abs_start)
            delay_ms = max(0, int(round((max(start, clip_abs_start) - start) * 1000)))
            label = f"c{j}"
            filters.append(
                f"[{j}:a]atrim=start={slice_start:.6f}:end={max(slice_start + 0.001, slice_end):.6f},"
                f"asetpts=PTS-STARTPTS,adelay={delay_ms}|{delay_ms}[{label}]"
            )
            mix_labels.append(f"[{label}]")
        filters.append(
            "".join(mix_labels)
            + f"amix=inputs={len(mix_labels)}:duration=first:dropout_transition=0:normalize=0,"
              f"atrim=duration={dur:.6f}[mix]"
        )
        cmd += [
            "-filter_complex", ";".join(filters),
            "-map", "[mix]", "-ac", "2", "-ar", str(SAMPLE_RATE),
            "-c:a", "pcm_s16le", str(out),
        ]
        _atomic_media_run(runner, cmd, out)
        progress(f"Rendering dub timeline: {n + 1}/{count}")

    progress("Combining dub timeline chunks…")
    concat = work_dir / f"timeline_concat_{timeline_signature}.txt"
    concat_lines = [f"file {_ffconcat_quote(chunk_path)}\n" for chunk_path in chunks]
    concat.write_text("".join(concat_lines), encoding="utf-8")
    _atomic_media_run(runner, [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(concat),
        "-c:a", "pcm_s16le", str(timeline),
    ], timeline)
    return timeline



def _merge_dialogue_guard_intervals(
    segments: Sequence[Segment],
    total_duration: float,
    pre: float = DIALOGUE_GUARD_PRE,
    post: float = DIALOGUE_GUARD_POST,
) -> List[Tuple[float, float]]:
    """Return merged regions where the dialogue-reduced stem should be used.

    The pre/post guard hides Demucs vocal bleed that begins slightly before or
    trails slightly after Whisper's speech timestamps.
    """
    intervals: List[Tuple[float, float]] = []
    limit = max(0.0, float(total_duration))
    for seg in segments:
        if not math.isfinite(seg.start) or not math.isfinite(seg.end):
            continue
        if seg.end <= seg.start:
            continue
        start = max(0.0, float(seg.start) - max(0.0, pre))
        end = min(limit, float(seg.end) + max(0.0, post))
        if end > start:
            intervals.append((start, end))
    if not intervals:
        return []
    intervals.sort()
    merged: List[List[float]] = [[intervals[0][0], intervals[0][1]]]
    for start, end in intervals[1:]:
        last = merged[-1]
        if start <= last[1] + 0.04:
            last[1] = max(last[1], end)
        else:
            merged.append([start, end])
    return [(a, b) for a, b in merged]


def build_dialogue_safe_background(
    original: Path,
    separated_background: Path,
    segments: Sequence[Segment],
    total_duration: float,
    work_dir: Path,
    config: Config,
    runner: CommandRunner,
    progress: ProgressCallback,
) -> Path:
    """Keep the untouched original soundtrack outside dialogue and use Demucs
    only around spoken regions.

    Demucs is a music-source separator, not a dialogue extractor. Using its
    no_vocals stem for an entire episode can remove score/SFX it misclassifies as
    vocal content. This hybrid bed restores the original music/SFX between lines
    while still suppressing the source-language dialogue around speech.
    """
    intervals = _merge_dialogue_guard_intervals(segments, total_duration)
    signature = hashlib.sha1(json.dumps({
        "original": [original.name, original.stat().st_size],
        "separated": [separated_background.name, separated_background.stat().st_size],
        "intervals": [[round(a, 3), round(b, 3)] for a, b in intervals],
        "chunk_seconds": int(config.chunk_seconds),
        "guard": [DIALOGUE_GUARD_PRE, DIALOGUE_GUARD_POST],
    }, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    out = work_dir / f"background_bed_{signature}.wav"
    if config.resume and _complete_wav(out, minimum_seconds=total_duration * .98) and not config.force:
        return out

    if not intervals:
        progress("No dialogue regions found; using original soundtrack as background…")
        _atomic_media_run(runner, [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(original), "-ac", "2", "-ar", str(SAMPLE_RATE),
            "-c:a", "pcm_s16le", str(out),
        ], out)
        return out

    progress("Restoring original music/SFX outside dialogue and suppressing source voices around speech…")
    chunk_seconds = max(30, int(config.chunk_seconds))
    chunk_dir = work_dir / f"background_chunks_{signature}"
    if chunk_dir.exists() and config.force:
        shutil.rmtree(chunk_dir)
    chunk_dir.mkdir(parents=True, exist_ok=True)
    chunks: List[Path] = []
    count = max(1, int(math.ceil(total_duration / chunk_seconds)))

    progress(f"Preparing music and effects: 0/{count}")
    for n in range(count):
        runner.check_cancel()
        start = n * chunk_seconds
        end = min(total_duration, (n + 1) * chunk_seconds)
        dur = max(0.01, end - start)
        chunk = chunk_dir / f"chunk_{n:05d}.wav"
        chunks.append(chunk)
        if config.resume and _complete_wav(chunk, minimum_seconds=dur * .98) and not config.force:
            progress(f"Preparing music and effects: {n + 1}/{count} (cached)")
            continue

        local: List[Tuple[float, float]] = []
        for a, b in intervals:
            if a >= end:
                break
            if b <= start:
                continue
            local.append((max(0.0, a - start), min(dur, b - start)))

        if not local:
            _atomic_media_run(runner, [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-ss", f"{start:.6f}", "-t", f"{dur:.6f}", "-i", str(original),
                "-ac", "2", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(chunk),
            ], chunk)
            progress(f"Preparing music and effects: {n + 1}/{count}")
            continue

        # Chunk-local expressions keep ffmpeg command size manageable even for
        # multi-hour episodes. Original is used outside speech; no_vocals inside.
        terms = "+".join(f"between(t,{a:.6f},{b:.6f})" for a, b in local)
        mask = f"gt({terms},0)"
        filt = (
            f"[0:a]atrim=duration={dur:.6f},asetpts=PTS-STARTPTS,"
            f"volume='if({mask},0,1)':eval=frame[o];"
            f"[1:a]atrim=duration={dur:.6f},asetpts=PTS-STARTPTS,"
            f"volume='if({mask},1,0)':eval=frame[s];"
            "[o][s]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
            "alimiter=limit=0.98[bed]"
        )
        _atomic_media_run(runner, [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{start:.6f}", "-t", f"{dur:.6f}", "-i", str(original),
            "-ss", f"{start:.6f}", "-t", f"{dur:.6f}", "-i", str(separated_background),
            "-filter_complex", filt, "-map", "[bed]",
            "-ac", "2", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(chunk),
        ], chunk)
        progress(f"Preparing music and effects: {n + 1}/{count}")

    progress("Combining music and effects chunks…")
    concat = work_dir / f"background_concat_{signature}.txt"
    concat.write_text("".join(f"file {_ffconcat_quote(x)}\n" for x in chunks), encoding="utf-8")
    _atomic_media_run(runner, [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(concat),
        "-c:a", "pcm_s16le", str(out),
    ], out)
    return out

def mix_background_and_dub(
    background: Path,
    dub: Path,
    work_dir: Path,
    config: Config,
    runner: CommandRunner,
    progress: ProgressCallback,
) -> Path:
    mix_signature = hashlib.sha1(json.dumps({
        "background": [background.name, background.stat().st_size],
        "dub": [str(dub), dub.stat().st_size],
        "background_volume": config.background_volume,
        "dub_volume": config.dub_volume,
        "ducking": config.ducking,
    }, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    out = work_dir / f"mixed_english_{mix_signature}.m4a"
    bg_duration = ffprobe_duration(background, runner)
    if config.resume and out.exists() and out.stat().st_size > 1000 and not config.force:
        try:
            if ffprobe_duration(out, runner) >= bg_duration * .98:
                return out
        except PipelineError:
            pass
    progress("Mixing dub dialogue with original music and sound effects…")
    temp = out.with_name(out.stem + ".partial" + out.suffix)
    temp.unlink(missing_ok=True)
    try:
        return _mix_to_temp(background, dub, temp, out, bg_duration, config, runner, progress)
    finally:
        temp.unlink(missing_ok=True)


def _mix_to_temp(background, dub, temp, out, bg_duration, config, runner, progress):
    if config.ducking:
        filt = (
            f"[0:a]volume={config.background_volume:.4f}[bg];"
            f"[1:a]volume={config.dub_volume:.4f},asplit=2[dub][sc];"
            "[bg][sc]sidechaincompress=threshold=0.060:ratio=1.8:attack=18:release=180[ducked];"
            "[ducked][dub]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
            "alimiter=limit=0.95,apad[mix]"
        )
        cp = runner.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(background), "-i", str(dub),
            "-filter_complex", filt, "-map", "[mix]",
            "-t", f"{bg_duration:.6f}", "-c:a", "aac", "-b:a", "192k", str(temp),
        ], check=False)
        if cp.returncode == 0:
            temp.replace(out)
            return out
        progress("Background ducking filter was unavailable; using a standard mix instead…")

    filt = (
        f"[0:a]volume={config.background_volume:.4f}[bg];"
        f"[1:a]volume={config.dub_volume:.4f}[dub];"
        "[bg][dub]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
        "alimiter=limit=0.95,apad[mix]"
    )
    runner.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(background), "-i", str(dub),
        "-filter_complex", filt, "-map", "[mix]",
        "-t", f"{bg_duration:.6f}", "-c:a", "aac", "-b:a", "192k", str(temp),
    ])
    temp.replace(out)
    return out


def mux_video(video: Path, audio: Path, final: Path, runner: CommandRunner, progress: ProgressCallback) -> None:
    final.parent.mkdir(parents=True, exist_ok=True)
    progress("Creating final dubbed MP4…")
    temp = final.with_name(final.stem + ".partial" + final.suffix)
    temp.unlink(missing_ok=True)
    try:
        _mux_to_temp(video, audio, temp, final, runner)
    finally:
        temp.unlink(missing_ok=True)


def _mux_to_temp(video: Path, audio: Path, temp: Path, final: Path, runner: CommandRunner) -> None:
    cp = runner.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(video), "-i", str(audio),
        "-map", "0:v:0?", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "copy", "-movflags", "+faststart",
        "-shortest", str(temp),
    ], check=False)
    if cp.returncode == 0:
        temp.replace(final)
        return
    # Fallback for source codecs that cannot be copied into MP4.
    codec = "h264_videotoolbox" if platform.system() == "Darwin" else "libx264"
    runner.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(video), "-i", str(audio),
        "-map", "0:v:0?", "-map", "1:a:0",
        "-c:v", codec, "-b:v", "6M", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", "-shortest", str(temp),
    ])
    temp.replace(final)


def doctor() -> Tuple[bool, List[str]]:
    checks: List[Tuple[str, bool, str]] = []
    checks.append(("macOS", platform.system() == "Darwin", platform.platform()))
    checks.append(("Apple Silicon", platform.machine() == "arm64", platform.machine()))
    for exe in ["ffmpeg", "ffprobe", "yt-dlp", "deno", "say"]:
        p = shutil.which(exe)
        checks.append((exe, bool(p), p or "not found"))
    for mod in ["mlx_whisper", "mlx_lm", "demucs", "numpy", "soundfile"]:
        try:
            __import__(mod)
            checks.append((mod, True, "import OK"))
        except Exception as e:
            checks.append((mod, False, f"import failed: {e}"))
    try:
        import speechbrain  # noqa: F401
        checks.append(("speechbrain", True, "optional ECAPA speaker model available"))
    except Exception as e:
        # Optional: v3 has a built-in acoustic clustering fallback.
        checks.append(("speechbrain", True, f"optional; fallback will be used ({e})"))
    try:
        import tkinter  # noqa: F401
        checks.append(("tkinter", True, "import OK"))
    except Exception as e:
        checks.append(("tkinter", False, f"import failed: {e}"))
    lines = [f"{'OK' if ok else 'FAIL':4}  {name:16} {detail}" for name, ok, detail in checks]
    return all(ok for _, ok, _ in checks), lines



def _character_map_path(config: Config, out: Path, key: str) -> Path:
    return out / f"{key}_characters.json"


def _profile_dict(profiles) -> Dict[str, dict]:
    return {p.id: p.to_dict() for p in profiles}


def analyze_only(config: Config, progress: Optional[ProgressCallback] = None, runner: Optional[CommandRunner] = None) -> Dict[str, Path]:
    progress = progress or print
    runner = runner or CommandRunner(progress)
    out = Path(config.output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    key = source_key(config.source)
    work = out / ".anime_dubber_work" / key; work.mkdir(parents=True, exist_ok=True)
    video = download_source(config.source, work, runner, progress)
    audio = extract_audio(video, work, runner, progress, config)
    vocals, _background = separate_dialogue(audio, work, runner, progress, config)
    segments = transcribe_audio(vocals, config, work, runner, progress, task="transcribe")
    if not segments:
        raise PipelineError("No Mandarin speech segments were detected after dialogue separation.")
    zh_srt = out / f"{key}_zh.srt"; write_srt(segments, zh_srt, translated=False)
    from .characters import analyze_characters, write_character_map
    char_path = _character_map_path(config, out, key)
    profiles, payload = analyze_characters(
        vocals, segments, work, out, runner, progress,
        resume=config.resume, force=config.force, max_speakers=config.max_speakers,
        speaker_threshold=config.speaker_threshold, series_id=config.series_id or key,
        available_voices=list_macos_voices(), override_path=char_path,
        speaker_backend=config.speaker_backend,
    )
    payload["characters"] = [p.to_dict() for p in profiles]
    write_character_map(payload, char_path)
    progress(f"DONE: {char_path}")
    return {"character_map": char_path, "chinese_srt": zh_srt}

def run_pipeline(config: Config, progress: Optional[ProgressCallback] = None, runner: Optional[CommandRunner] = None) -> Dict[str, Path]:
    progress = progress or print
    runner = runner or CommandRunner(progress)
    out = Path(config.output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    key = source_key(config.source)
    work = out / ".anime_dubber_work" / key
    version_dir = out / "versions" / config.version_id if config.version_id else out
    version_dir.mkdir(parents=True, exist_ok=True)
    def publish(kind: str, path: Path, language: str) -> None:
        callback = getattr(runner, "artifact", None)
        if callback:
            callback(kind, path, language)
    if config.force and work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)

    video = download_source(config.source, work, runner, progress)
    publish("source_video", video, config.source_language)
    audio = extract_audio(video, work, runner, progress, config)

    if config.mode == "dub":
        vocals, background = separate_dialogue(audio, work, runner, progress, config)
        transcript_audio = vocals
    else:
        vocals = audio
        background = audio
        transcript_audio = audio

    zh_segments = transcribe_audio(transcript_audio, config, work, runner, progress, task="transcribe")
    if not zh_segments:
        raise PipelineError("No Mandarin speech segments were detected. Try the original soundtrack, a different source, or --force to rebuild cached separation.")
    zh_srt = out / f"{key}_zh.srt"
    write_srt(zh_segments, zh_srt, translated=False)
    zh_vtt = out / f"{key}_zh.vtt"
    write_vtt(zh_segments, zh_vtt, translated=False)
    publish("chinese_srt", zh_srt, "zh")
    publish("chinese_vtt", zh_vtt, "zh")

    translation_mode = config.translation
    if translation_mode == "auto":
        if platform.system() == "Darwin" and platform.machine() == "arm64":
            try:
                import mlx_lm  # noqa: F401
                translation_mode = "llm"
            except Exception:
                translation_mode = "whisper"
        else:
            translation_mode = "ollama" if config.target_language != "en" else "whisper"
    if config.target_language != "en" and translation_mode == "whisper":
        raise PipelineError("Whisper direct translation only supports English; choose LLM or Ollama.")
    if config.review_before_dub and config.mode == "dub" and translation_mode == "whisper":
        raise PipelineError("Automatic subtitle review needs line-aligned LLM or Ollama translation. Choose one of those providers or turn off review.")

    if translation_mode == "llm":
        segments = translate_with_llm(zh_segments, config, work, runner, progress)
    elif translation_mode == "ollama":
        segments = translate_with_ollama_provider(zh_segments, config, work, runner, progress)
    elif translation_mode == "whisper":
        en_whisper = transcribe_audio(transcript_audio, config, work, runner, progress, task="translate")
        segments = [Segment(s.start, s.end, s.text, s.text) for s in en_whisper]
    else:
        raise PipelineError(f"Unsupported translation mode: {translation_mode}")

    # Subtitles are usable output in their own right. Publish them before voice
    # analysis so a slow or failed speaker pass cannot hold back the files.
    en_srt = version_dir / f"{key}_{config.target_language}.srt"
    write_srt(segments, en_srt, translated=True)
    en_vtt = version_dir / f"{key}_{config.target_language}.vtt"
    write_vtt(segments, en_vtt, translated=True)
    publish("translated_srt", en_srt, config.target_language)
    publish("translated_vtt", en_vtt, config.target_language)
    results: Dict[str, Path] = {"chinese_srt": zh_srt, "chinese_vtt": zh_vtt,
                                "translated_srt": en_srt, "translated_vtt": en_vtt}
    if config.target_language == "en":
        results["english_srt"] = en_srt

    # Publish a fast, nonblocking quality report at the subtitle boundary.
    # Stronger model suggestions can be added to this report later with the CLI
    # without rerunning transcription, translation, or TTS.
    from .review import review_subtitles
    review_path = en_srt.with_suffix(".review.json")
    approval_path = version_dir / f"{key}_{config.target_language}.review-approval.json"
    try:
        review = review_subtitles(zh_srt, en_srt, review_path, language=config.target_language,
                                  context=config.context, glossary=config.glossary,
                                  progress=progress)
        results["review_report"] = review_path
        publish("review_report", review_path, config.target_language)
        progress(f"Subtitle review: {review['flagged_cues']} cues flagged; report: {review_path}")
    except (OSError, ValueError) as exc:
        progress(f"Warning: subtitle review skipped: {exc}")
        if config.review_before_dub and config.mode == "dub":
            raise PipelineError(f"Cannot prepare subtitle review: {exc}") from exc

    if config.review_before_dub and config.mode == "dub" and review["priority_cues"]:
        from .review import approved_revisions
        decisions = approved_revisions(approval_path, review, len(segments))
        if decisions is None:
            if platform.system() != "Darwin" or platform.machine() != "arm64":
                raise PipelineError("Automatic MLX review requires an Apple silicon Mac. Disable review or run the CLI review separately.")
            progress("Reviewing flagged subtitles with stronger local models…")
            args = [sys.executable, "-m", "anime_dubber.cli", "review-subtitles", str(zh_srt),
                    str(en_srt), "--report", str(review_path), "--target-language", config.target_language,
                    "--model", config.review_model, "--audio", str(transcript_audio),
                    "--context", config.context, "--glossary-json", json.dumps(config.glossary, ensure_ascii=False)]
            try:
                runner.run(args)
            except CancelledError:
                raise
            except (PipelineError, OSError) as exc:
                progress(f"Warning: stronger subtitle review failed; the original subtitles and flagged report remain available: {exc}")
                review = json.loads(review_path.read_text(encoding="utf-8"))
                review["review_error"] = str(exc)
                _atomic_json_write(review_path, review)
            review = json.loads(review_path.read_text(encoding="utf-8"))
            publish("review_report", review_path, config.target_language)
            progress("Subtitle suggestions are ready. Review them in Dub Details, then continue this dub.")
            raise ReviewRequired("Subtitle review required before voice generation")
        for idx, value in decisions.items():
            segments[idx].translated = value
        if decisions:
            write_srt(segments, en_srt, translated=True)
            write_vtt(segments, en_vtt, translated=True)
            publish("translated_srt", en_srt, config.target_language)
            publish("translated_vtt", en_vtt, config.target_language)
            progress(f"Applied {len(decisions)} approved subtitle revisions")

    if config.mode == "subtitles":
        progress(f"DONE: {en_srt}")
        return results

    profiles = []
    profile_map: Dict[str, dict] = {}
    char_path = _character_map_path(config, out, key)
    if config.mode == "dub" and config.multi_character:
        from .characters import analyze_characters, write_character_map
        # Analyze against Chinese timestamps. If Whisper-direct translation changed segmentation,
        # transfer speaker/style labels to the closest English segment by midpoint overlap.
        profiles, payload = analyze_characters(
            vocals, zh_segments, work, out, runner, progress,
            resume=config.resume, force=config.force, max_speakers=config.max_speakers,
            speaker_threshold=config.speaker_threshold, series_id=config.series_id or key,
            available_voices=list_macos_voices(), override_path=char_path,
            speaker_backend=config.speaker_backend,
            make_voice_references=config.auto_voice_references and config.target_language == "en"
                                  and config.tts_engine in {"auto", "chatterbox"},
        )
        if segments is not zh_segments:
            for seg in segments:
                mid = (seg.start + seg.end) / 2.0
                candidates = [z for z in zh_segments if z.start <= mid <= z.end]
                if not candidates and zh_segments:
                    candidates = [min(zh_segments, key=lambda z: abs(((z.start + z.end) / 2.0) - mid))]
                if candidates:
                    seg.speaker_id = candidates[0].speaker_id
                    seg.style = candidates[0].style
                    seg.style_confidence = candidates[0].style_confidence
        payload["characters"] = [p.to_dict() for p in profiles]
        write_character_map(payload, char_path)
        profile_map = _profile_dict(profiles)
        progress(f"Character map: {char_path}")

    if profiles:
        snapshot_map = version_dir / f"{key}_characters.json" if config.version_id else char_path
        if snapshot_map != char_path:
            shutil.copy2(char_path, snapshot_map)
        results["character_map"] = snapshot_map
        publish("character_map", snapshot_map, config.target_language)

    tts_dir = work / f"tts_{config.tts_engine}_{config.version_id}" if config.version_id else work / f"tts_{config.tts_engine}"
    clips: List[Path] = []
    total_lines = len(segments)
    for i, seg in enumerate(segments):
        runner.check_cancel()
        profile = profile_map.get(seg.speaker_id, {}) if config.multi_character else {}
        clips.append(prepare_tts_clip(seg, i, tts_dir, config, runner, progress, profile=profile))
        if (i + 1) % 5 == 0 or i + 1 == total_lines:
            who = f" ({seg.speaker_id}, {seg.style})" if seg.speaker_id else ""
            reused = getattr(runner, "reused_voice_clips", 0)
            progress(f"Generating dub voice: {i + 1}/{total_lines}{who} · {reused} reused")

    total_duration = ffprobe_duration(audio, runner)
    duration_callback = getattr(runner, "duration", None)
    if duration_callback:
        duration_callback(total_duration)
    dub_timeline = render_dub_timeline(segments, clips, total_duration, work, config, runner, progress)
    background_bed = build_dialogue_safe_background(
        audio, background, zh_segments, total_duration, work, config, runner, progress
    )
    mixed = mix_background_and_dub(background_bed, dub_timeline, work, config, runner, progress)
    final = version_dir / f"{key}_{config.target_language.upper()}_DUB.mp4"
    mux_video(video, mixed, final, runner, progress)
    results["dubbed_video"] = final
    exported_audio = version_dir / f"{key}_{config.target_language.upper()}_DUB.m4a"
    if mixed != exported_audio:
        shutil.copy2(mixed, exported_audio)
    results["dub_audio"] = exported_audio
    publish("dubbed_video", final, config.target_language)
    publish("dub_audio", exported_audio, config.target_language)

    metadata = {
        "source": config.source,
        "mode": config.mode,
        "asr_provider": config.asr_provider,
        "faster_whisper_model": config.faster_whisper_model,
        "translation": config.translation,
        "ollama_model": config.ollama_model if config.translation == "ollama" else None,
        "tts_engine": config.tts_engine,
        "auto_voice_references": config.auto_voice_references,
        "chatterbox_reference_audio": config.chatterbox_reference_audio,
        "piper_model": config.piper_model if config.tts_engine in {"piper", "auto"} else None,
        "multi_character": config.multi_character,
        "series_id": config.series_id or key,
        "max_speakers": config.max_speakers,
        "speaker_threshold": config.speaker_threshold,
        "speaker_backend": config.speaker_backend,
        "review_before_dub": config.review_before_dub,
        "review_model": config.review_model if config.review_before_dub else None,
        "whisper_model": WHISPER_MODEL,
        "llm_model": LLM_MODEL if config.translation == "llm" else None,
        "demucs_model": DEMUCS_MODEL,
        "glossary": config.glossary,
    }
    (version_dir / f"{key}_run.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    if not config.keep_work:
        try:
            shutil.rmtree(work)
        except Exception:
            progress(f"Warning: could not remove work directory: {work}")
    progress(f"DONE: {final}")
    return results
