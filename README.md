# AnimeDubber v4 alpha

AnimeDubber turns Chinese animation / manhua-drama videos into English-subtitled or English-dubbed videos while preserving the original soundtrack as much as possible.

v4 is being rebuilt around a **native SwiftUI macOS frontend + shared Python application service + cross-platform CLI**.

The complete design is documented in:

```text
docs/SWIFTUI_REDESIGN_SPEC.md
```

## Current v4 alpha status

Phase 3 is underway and now includes:

- a shared Python `ApplicationService` used as the boundary for future SwiftUI and CLI callers;
- structured jobs and structured progress/events;
- a newline-delimited JSON stdin/stdout transport for the future SwiftUI app;
- a restored Python CLI;
- a native SwiftUI macOS shell connected to the Python backend;
- persistent lightweight project manifests and project history;
- a native Projects table with status, artifacts, and resume-oriented settings reuse;
- a native Characters table and inspector for editing voice assignments;
- persistent manual character overrides synchronized back to the series voice database;
- cancellation and job snapshots;
- provider/capability detection;
- tests for the service, protocol, and CLI;
- all existing v3.4 timestamp/TTS reliability fixes;
- all existing v3.5 soundtrack restoration fixes.

The existing Tkinter GUI is still present **temporarily** as a fallback while SwiftUI reaches full feature parity. The SwiftUI New Dub, Projects, Activity, System Check, and Characters workflows are now implemented.

## CLI

The CLI is back as a permanent interface.

Cross-platform command syntax:

```bash
python -m anime_dubber.cli doctor
python -m anime_dubber.cli capabilities
python -m anime_dubber.cli analyze VIDEO --series-id my-series
python -m anime_dubber.cli run VIDEO --output ./output --series-id my-series
```

On Apple-silicon macOS, the existing MLX/macOS processing engine remains available.

The CLI/application-service boundary itself is cross-platform. Windows/Linux processing providers such as Faster-Whisper and Piper are the next provider phase; the current legacy processing engine underneath the service is still macOS/MLX-specific. `doctor` and `capabilities` already expose this distinction instead of pretending unsupported providers are available.

## SwiftUI backend protocol

During development the future SwiftUI app will launch:

```bash
.venv/bin/python -m anime_dubber.transport.stdio_server
```

Communication is newline-delimited JSON over stdin/stdout, so AnimeDubber does not need a localhost HTTP server or network port.

Example request:

```json
{"type":"request","id":"42","method":"hello","params":{}}
```

Example response:

```json
{"type":"response","id":"42","ok":true,"result":{"backend":"AnimeDubber","version":"4.0.0a2","protocol_version":1}}
```

Long-running jobs send asynchronous event messages for stages, progress, logs, warnings, artifacts, errors, and completion.

## Audio behavior retained from v3.4/v3.5

- malformed / reversed Whisper timestamps are sanitized before SRT and TTS;
- duplicate micro-segments are collapsed;
- zero-sample TTS clips are rejected;
- TTS lead-in silence is trimmed;
- the untouched original soundtrack is preserved outside dialogue;
- Demucs `no_vocals` is used only around detected source dialogue, with guard padding to reduce voice bleed;
- optional ducking is intentionally gentle and off by default.

## Native SwiftUI macOS app

After setup, run the current native frontend from the repository:

```bash
cd macos/AnimeDubberApp
swift run
```

During development the Swift app finds the repository root, launches the existing `.venv` Python backend, and communicates over JSONL stdin/stdout.

Projects are stored as lightweight manifests under:

```text
.anime_dubber_project/
```

Existing v3.x `*_run.json` jobs are automatically surfaced in the Projects screen, so old completed jobs do not need to be reprocessed.

Character overrides made in SwiftUI are written to the existing `*_characters.json` map and synchronized to `.anime_dubber_series/` so the same character voice persists across episodes.

## Current macOS install

From Terminal:

```bash
cd /path/to/AnimeDubberMac
/bin/zsh setup.sh
```

The temporary Tkinter GUI can still be launched with:

```text
Run GUI.command
```

or:

```bash
.venv/bin/python -m anime_dubber.gui
```

## Current generated files

Typical output:

- `<key>_zh.srt` — Mandarin transcript
- `<key>_en.srt` — English subtitles
- `<key>_characters.json` — character / voice assignments
- `<key>_EN_DUB.mp4` — final English dub
- `<key>_run.json` — run metadata

Cached processing remains under:

```text
.anime_dubber_work/
```

Persistent series character data remains under:

```text
.anime_dubber_series/
```

Existing caches are intentionally preserved through the v4 migration where compatible.

## Current models / software

- MLX Whisper: `mlx-community/whisper-large-v3-turbo`
- Local translator: `mlx-community/Qwen3-4B-Instruct-2507-4bit`
- Demucs: `htdemucs`
- Optional speaker encoder: `speechbrain/spkrec-ecapa-voxceleb`
- macOS local TTS: `say`
- Video/audio processing: FFmpeg
- YouTube retrieval: app-local yt-dlp

Planned cross-platform providers are documented in the SwiftUI redesign spec.
