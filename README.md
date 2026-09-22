# AnimeDubber v4 alpha

AnimeDubber turns Chinese animation / manhua-drama videos into English-subtitled or English-dubbed videos while preserving the original soundtrack as much as possible.

The architecture is now:

```text
Native SwiftUI macOS app ─┐
                          ├── Python ApplicationService ── pipeline/providers
Cross-platform CLI ───────┘
```

The approved design lives in:

```text
docs/SWIFTUI_REDESIGN_SPEC.md
```

## Current v4 status

Phase 6 now includes:

- native SwiftUI macOS frontend;
- persistent Projects history;
- native Characters table + inspector;
- shared Python backend for SwiftUI and CLI;
- JSONL stdin/stdout backend transport;
- structured progress, cancellation, diagnostics, and artifacts;
- MLX Whisper / MLX LLM / macOS voices on Apple silicon;
- Faster-Whisper / Ollama / Piper providers for Windows and Linux;
- Demucs CUDA fallback on supported NVIDIA systems;
- provider configuration from the macOS Settings window;
- persistent macOS app preferences;
- ElevenLabs API key stored in macOS Keychain;
- local `.app` packaging and installation;
- Chatterbox Turbo as the preferred high-quality local voice engine;
- Kokoro as the fast lightweight local voice engine;
- optional per-character voice engine, reference clip, expressiveness, and Kokoro preset overrides;
- automatic voice priority: Chatterbox → Kokoro → platform fallback;
- existing v3.4 timestamp/TTS reliability fixes;
- existing v3.5 soundtrack-preservation fixes.

The old Tkinter GUI has been removed. The CLI remains permanently for Windows, Linux, automation, and headless workflows.

## macOS install

Apple Silicon macOS 14+:

```bash
cd /path/to/AnimeDubberMac
/bin/zsh setup.sh
```

Setup installs the Python dependencies, runs the tests and backend checks, then builds and installs:

```text
~/Applications/AnimeDubber.app
```

Open it normally from Finder or Spotlight.

To rebuild only the native app:

```bash
/bin/zsh macos/package_app.sh --install
```

To build, install, and immediately open it:

```bash
/bin/zsh macos/package_app.sh --install --open
```

### Why the macOS app is large

The local packaged app embeds the existing Python virtual environment so it can launch the backend without `swift run` or a Terminal window. That environment contains ML/audio dependencies and can be around 2 GB.

Model weights are **not** copied into the app. MLX / Hugging Face model caches remain in their normal user cache locations.

The current packager is intended for a local build on the same Mac. A future signed/notarized public release can move to a dedicated relocatable Python runtime.

## macOS Settings

The native Settings window now controls:

- ASR provider: Automatic / MLX Whisper / Faster-Whisper
- translation: Automatic / local MLX LLM / Ollama / Whisper direct
- TTS: Automatic / Chatterbox Turbo / Kokoro / ElevenLabs / macOS / Piper
- Faster-Whisper model, device, and compute type
- Ollama URL and model
- Chatterbox device, Turbo mode, expressiveness, and optional reference clip
- Kokoro voice preset
- Piper voice model and speaker ID
- fallback macOS voice and speaking rate
- default output folder / series ID
- speaker detection and audio defaults

The ElevenLabs API key is stored in **macOS Keychain**. It is not written to project manifests.

## Premium local voices

Install the optional premium local voice engines into AnimeDubber's existing environment:

```bash
/bin/zsh macos/install_voice_engines.sh
```

That installer adds:

- **Chatterbox Turbo** for the highest-quality local English character speech and optional zero-shot voice cloning;
- **Kokoro** for much faster lightweight local speech;
- `espeak-ng`, which Kokoro uses for English text processing.

The installer then runs the test suite and rebuilds `~/Applications/AnimeDubber.app` so the installed app contains those Python packages.

When **Automatic · Best Local** is selected, AnimeDubber uses:

```text
Chatterbox Turbo
      ↓ unavailable
Kokoro
      ↓ unavailable
macOS / Piper / ElevenLabs fallback
```

Each analyzed character can override the app default in **Characters → English Voice**. Chatterbox reference audio is never extracted or assigned automatically: only a clip explicitly selected by the user is used as a cloning reference. Use reference voices you have permission to use.

## CLI

The CLI remains a first-class interface:

```bash
python -m anime_dubber.cli doctor
python -m anime_dubber.cli capabilities
python -m anime_dubber.cli analyze VIDEO --series-id my-series
python -m anime_dubber.cli run VIDEO --output ./output --series-id my-series
```

### Windows / Linux

Install FFmpeg / ffprobe on PATH first.

Linux:

```bash
bash setup-cross-platform.sh
```

Windows PowerShell:

```powershell
.\setup-cross-platform.ps1
```

Example local Windows/Linux dub:

```bash
python -m anime_dubber.cli run VIDEO \
  --output ./output \
  --asr faster-whisper \
  --translation whisper \
  --tts piper \
  --piper-model /path/to/en_US-voice.onnx
```

With Ollama translation:

```bash
python -m anime_dubber.cli run VIDEO \
  --output ./output \
  --asr faster-whisper \
  --translation ollama \
  --ollama-model qwen3:4b \
  --tts piper \
  --piper-model /path/to/en_US-voice.onnx
```

Piper requires a compatible English `.onnx` voice model. Ollama is optional. ElevenLabs remains available as an alternative TTS provider.

## SwiftUI ↔ Python backend

The native app launches:

```text
anime_dubber.transport.stdio_server
```

from the backend bundled inside the app. Development builds can still locate the repository backend automatically.

Communication is newline-delimited JSON over stdin/stdout. No localhost server or open network port is required.

Example:

```json
{"type":"request","id":"42","method":"hello","params":{}}
```

The backend emits structured stage, progress, log, warning, artifact, error, and completion events.

## Audio behavior

AnimeDubber retains the v3.4/v3.5 fixes:

- malformed / reversed Whisper timestamps are sanitized;
- duplicate micro-segments are collapsed;
- zero-sample TTS clips are rejected;
- TTS lead-in silence is trimmed;
- untouched original soundtrack is preserved outside dialogue;
- Demucs `no_vocals` is used only around detected source dialogue;
- pre/post dialogue guards reduce source-voice bleed;
- background ducking is gentle and off by default.

## Project data

Typical output:

- `<key>_zh.srt`
- `<key>_en.srt`
- `<key>_characters.json`
- `<key>_EN_DUB.mp4`
- `<key>_run.json`

Heavy resumable work remains in:

```text
.anime_dubber_work/
```

Persistent series character data:

```text
.anime_dubber_series/
```

Lightweight project manifests / logs:

```text
.anime_dubber_project/
```

Existing compatible caches are reused during the v4 migration.

## Core providers

Apple Silicon macOS:

- ASR: MLX Whisper
- translation: `mlx-community/Qwen3-4B-Instruct-2507-4bit`
- preferred local TTS: Chatterbox Turbo when installed
- fast local TTS: Kokoro when installed
- compatibility fallback: macOS `say`

Windows / Linux:

- ASR: Faster-Whisper
- translation: Whisper direct or Ollama
- premium local TTS: Chatterbox / Kokoro when installed
- lightweight fallback: Piper

Shared:

- Demucs
- optional SpeechBrain ECAPA speaker encoder
- FFmpeg
- yt-dlp
- optional ElevenLabs TTS
