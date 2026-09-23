# AnimeDubber v4 alpha

The next workspace version uses **Project → Source → Subtitles → Dub versions → Outputs**. See [project workspace design and migration](docs/PROJECT_WORKSPACE_VNEXT.md) for the UI audit, versioned output structure, legacy migration and language/provider limits.

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

Setup installs the Python dependencies, runs the tests and backend checks, then updates an existing app in `/Applications` or `~/Applications`. If neither exists, it installs:

```text
~/Applications/AnimeDubber.app
```

Open it normally from Finder or Spotlight.

To rebuild only the native app:

```bash
/bin/zsh macos/package_app.sh --install
```

Installing removes the temporary app bundle from `dist` after the install succeeds.
Run `macos/package_app.sh` without `--install` if you want an app bundle in `dist`.

To build, install, and immediately open it:

```bash
/bin/zsh macos/package_app.sh --install --open
```

If both locations contain an app, the installer asks for an explicit destination instead of guessing. To replace an app elsewhere, pass its full path, for example:

```bash
zsh macos/package_app.sh --install-to "/Applications/AnimeDubber.app" --open
```

Run `zsh macos/package_app.sh --install --print-install-target` to see the location the installer would update. Quit the running app before rebuilding it.

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

When English dubbing uses Chatterbox and speaker detection is enabled, **Choose character voice clips automatically** extracts short, isolated source dialogue for each character. Run **Analyze Characters** first to listen to each chosen clip in **Characters → English Voice** and replace or disable a bad match before generating the dub. A character without enough clean speech uses the configured default voice. A manually chosen character reference takes priority, followed by the global Chatterbox reference, then the automatic clip. The selected clips and timestamps remain in the project work folder and character map for later review and resume. Use `--no-auto-source-voices` to disable this from the CLI.

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
- optional full Whisper Large v3 and Qwen3 8B/14B or experimental Qwen3.5 9B in New Dub and Settings
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

## Project workspace CLI

```bash
python -m anime_dubber.cli new-project /path/to/source.mp4 -o ~/Movies/AnimeDubber --name "Episode 1"
python -m anime_dubber.cli run /path/to/source.mp4 -o ~/Movies/AnimeDubber --dub-name "English — Chatterbox" --tts chatterbox
python -m anime_dubber.cli run /path/to/source.mp4 -o ~/Movies/AnimeDubber --subtitles-only --target-language es --translation ollama
python -m anime_dubber.cli projects -o ~/Movies/AnimeDubber
python -m anime_dubber.cli resume-dub PROJECT_ID DUB_ID -o ~/Movies/AnimeDubber
```

Each `run` creates a version. Its translated SRT/VTT appears under `versions/<version-id>/` before dubbing finishes. Non-English dub audio currently requires `--tts elevenlabs` and a multilingual ElevenLabs voice; for other languages without that provider, use `--subtitles-only`.

Use **Pause** while a dub is processing, then **Resume This Dub** in Dub Details. Failed jobs can also be resumed there. Resume preserves the dub ID and completed source, subtitles, translation batches, and voice clips whose settings still match. The operation in progress may need to restart; a model call may finish before the pause takes effect. Restarting the app after a crash also leaves the interrupted dub available to resume. Keep the project's `.anime_dubber_work` directory to retain these checkpoints. For ElevenLabs dubs, re-enter the API key in Settings or pass `--elevenlabs-api-key` when resuming from CLI.

### Selective subtitle review and Mac speed sample

Run this after the Chinese and translated SRT files have appeared. It does not change the dub currently processing or overwrite the subtitles. The first pass only detects likely transcription, translation, and timing issues:

```bash
python -m anime_dubber.cli review-subtitles \
  ~/Movies/AnimeDubber/VIDEO_ID_zh.srt \
  ~/Movies/AnimeDubber/versions/DUB_ID/VIDEO_ID_en.srt
```

To measure the *additional* cost of the stronger translation review on your Mac, pause the dub or wait for it to finish before loading a second model on a 16 GB machine. Start with an 8B model that works with the app's existing `mlx-lm` dependency; test the first five minutes:

```bash
python -m anime_dubber.cli review-subtitles \
  ~/Movies/AnimeDubber/VIDEO_ID_zh.srt \
  ~/Movies/AnimeDubber/versions/DUB_ID/VIDEO_ID_en.srt \
  --sample-seconds 300 --model mlx-community/Qwen3-8B-4bit
```

The command prints elapsed model-load and review time and saves a `.review.json` next to the translated SRT. On a subsequent invocation with the same inputs, completed suggestions are reused. Remove `--sample-seconds 300` to process remaining flagged cues. For a second transcription of suspicious source lines, add `--audio /path/to/extracted_dialogue.wav`; this loads the full Whisper Large v3 model and records its own timing. Use the separated dialogue WAV where possible. The alternate transcription and proposed translations are **unverified suggestions** in the report, not automatic changes to the existing SRT or dub. Model downloads are required on first use; this test measures incremental review cost, not the speed of full transcription or TTS.

For a new dub on Apple silicon, enable **Review flagged lines before voices** in New Dub, or pass `--review-before-dub` to the CLI. The app saves both SRTs, runs the larger local translation model and a second transcription of the most suspicious speech cues, then pauses before voice generation. In Dub Details, compare each priority cue and choose its wording, then select **Approve and Continue Dub**. An unchanged line keeps its original translation. The decision and model suggestions are saved per dub so interrupted review can resume without redoing transcription or translation. The setting is opt-in because the first model downloads and the review pass can add substantial time on a 16 GB Mac.

For headless jobs, inspect the `*.review.json` file, then run `python -m anime_dubber.cli approve-review PROJECT_ID DUB_ID -o OUTPUT_DIR` to keep the original lines, or pass `--revisions corrections.json` with a JSON object such as `{"199": "Approved line"}`. Finally run `python -m anime_dubber.cli resume-dub PROJECT_ID DUB_ID -o OUTPUT_DIR`. If a stronger model fails, the job still pauses with the saved original subtitles and a warning; you can approve the original text or edit it before continuing.

Voice clips now play at their generated pace and may continue beyond the subtitle end if there is room before the next cue. If a clip would overlap the next cue or run past the video's end, the dub pauses at that cue, saves the completed clips, and asks for a shorter translation. On Apple silicon it requests a stronger-model suggestion for that cue; its proposed wording still needs your review and the new voice duration is checked again on resume. No speech is accelerated or cut to fit. Select full Whisper Large v3 and a larger translation model in New Dub, or supply model IDs in Settings. A model choice starts applying to a new dub; an existing rendered video keeps its audio.
