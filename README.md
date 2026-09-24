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
- Chatterbox voice cloning as the preferred local voice engine (Standard with accent mitigation for Chinese references dubbed into English, Turbo otherwise);
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

Setup installs the Python dependencies, runs the tests and backend checks, then installs the app at:

```text
/Applications/AnimeDubber.app
```

Open it normally from Finder or Spotlight.

### Dub a video

Open **Dub a Video**, paste the video's normal page URL or choose/drop a local file, select the language, and click **Dub Video**. The app checks the required tools, creates a project, generates subtitles and voices, and opens the finished video. The progress screen shows the current stage; its percentage describes that stage rather than the entire job. Use **Save Video…** on the result page to export the finished movie.

English uses the automatic local voice path by default. Other dubbing languages currently require selecting ElevenLabs under Settings → Providers and adding an API key. A model or tool missing from the Mac is reported before the job starts; use **System Check** for details. Voice, subtitle, and timing changes can be inspected later in the project's dub details.

To rebuild only the native app:

```bash
/bin/zsh macos/package_app.sh --install
```

Installing removes the temporary app bundle from `dist` and any old copy in `~/Applications` after the install succeeds.
Run `macos/package_app.sh` without `--install` if you want an app bundle in `dist`.

To build, install, and immediately open it:

```bash
/bin/zsh macos/package_app.sh --install --open
```

To install elsewhere, pass the full destination path, for example:

```bash
zsh macos/package_app.sh --install-to "$HOME/Applications/AnimeDubber.app" --open
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
- TTS: Automatic / Chatterbox Voice Clone / Kokoro / ElevenLabs / macOS / Piper
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

- **Chatterbox** for English character speech and optional zero-shot voice cloning; Chinese references use the Standard model with CFG weight zero to reduce source accent transfer into English (at a speed cost);
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

When English dubbing uses Chatterbox and speaker detection is enabled, **Choose character voice clips automatically** combines at least 5.25 seconds of isolated source dialogue for each character. Run **Analyze Characters** first to listen to each chosen clip in **Characters → English Voice** and replace or disable a bad match before generating the dub. A character without enough clean speech uses a Kokoro or macOS character voice. A manually chosen character reference takes priority, followed by the global Chatterbox reference, then the automatic clip. References shorter than 5.25 seconds fall back to a character voice instead of stopping the dub. The selected clips and timestamps remain in the project work folder and character map for later review and resume. Use `--no-auto-source-voices` to disable this from the CLI.

English dubs default to reducing accent transfer from Chinese source clips. This keeps the source speaker as a reference but cannot guarantee a US accent or identical voice identity. It uses Chatterbox Standard even if Turbo is selected and can run slower. For an American preset voice, choose Kokoro for that character; this does not clone the original voice. CLI users can pass `--preserve-source-accent` to disable accent mitigation.

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
- lines that overrun the next voice get up to three shorter model rewrites, each measured with the selected voice; if none fits naturally, the app tries pitch-preserving speedup capped at 1.5×, then keeps the full voice with a logged overlap if the gap is physically too short;
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
- transcription: full Whisper Large v3 by default; Turbo remains a faster option
- translation and automatic subtitle review: `mlx-community/Qwen3-8B-4bit` by default on supported Macs; 4B remains a faster option and 14B remains a high-memory option
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

For a new dub on Apple silicon, **Automatically check and correct subtitles** is enabled by default. The app saves both SRTs, runs the local review model and a second transcription for suspicious speech, applies plausible corrections, and continues without a review pause. The report records alternate hypotheses and automatic changes; a short disputed cue cannot be guaranteed correct by any speech model. Models download on first use, and the review adds processing time on a 16 GB Mac. Use `--no-auto-review` to disable it in the CLI.

For headless jobs, inspect the `*.review.json` file for the automatic corrections and unresolved uncertainty after the dub. If a review model fails, the job continues with the original translation and reports the failure. `approve-review` and `resume-dub` remain available for older paused versions.

Voice clips may continue beyond the subtitle end if there is room before the next cue. When a clip would overlap the next voice or run past the video's end, the app tries up to three shorter translations and measures each rendered voice. If they still cannot fit naturally, it tries pitch-preserving speedup up to 1.5×. When the gap is too short even then, the app keeps the full sped-up line and reports any audible overlap. For an overlong final line, it extends the video with a held final frame so the words are not cut. This is a best-effort automatic result, and tightly spaced speech can still sound crowded. New model choices apply to new dubs; an existing rendered video keeps its audio.
