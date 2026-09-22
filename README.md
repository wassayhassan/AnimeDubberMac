# AnimeDubber v3.6

A macOS-first app for turning Chinese animation / manhua-drama videos into English-subtitled or English-dubbed videos while preserving the original soundtrack as much as possible.

## v3.6

v3.6 is GUI-only. The old command-line interface has been removed.

The main window was redesigned around a cleaner macOS-style workflow:

- Project source, output folder, and Series ID are kept at the top.
- General, Voices, and Audio settings are separated into tabs.
- Character analysis and the Character Voices editor remain available from the main window.
- Processing status and download progress are easier to scan.
- The Activity log now renders real line breaks correctly, supports word wrapping, scrolling, error highlighting, and clearing.
- The UI defaults to background ducking off.

## Audio behavior

The v3.4 reliability fixes and v3.5 soundtrack fixes are retained:

- malformed / reversed Whisper timestamps are sanitized before SRT and TTS;
- duplicate micro-segments are collapsed;
- zero-sample TTS clips are rejected;
- TTS lead-in silence is trimmed;
- the untouched original soundtrack is preserved outside dialogue;
- Demucs `no_vocals` is used only around detected source dialogue, with guard padding to reduce voice bleed;
- optional ducking is intentionally gentle.

## Main features

- Multi-character speaker analysis.
- Persistent character voices across episodes using the same **Series ID**.
- Lead / major / supporting / minor role estimates.
- Child / adult / older and masculine / feminine / neutral voice-style estimates.
- Normal / shouting / whispering delivery detection.
- Automatic macOS voice assignment.
- Optional ElevenLabs output.
- Editable Character Voices window for manual overrides.
- Local MLX Whisper transcription.
- Local MLX LLM translation.
- YouTube download progress with percentage, speed, ETA, and fallback attempt.
- Resume support for long jobs.

## Install on Apple silicon macOS

From Terminal:

```bash
cd /path/to/AnimeDubberMac
/bin/zsh setup.sh
```

The setup installs/checks the required system and Python dependencies, runs the bundled tests, and performs a system check.

After setup, launch the app by double-clicking:

```text
Run GUI.command
```

or from Terminal:

```bash
.venv/bin/python -m anime_dubber.gui
```

## Recommended settings

For a long-form dub:

- Translation: **Local LLM**
- Detect speakers: **On**
- Speaker backend: **auto**
- TTS: **macOS local**
- Background ducking: **Off**
- Music / SFX: **1.0**
- Resume cached work: **On**

Use **Analyze Characters** first if you want to review voice assignments before rendering the complete dub.

## Files produced

Typical output:

- `<key>_zh.srt` — Mandarin transcript
- `<key>_en.srt` — English subtitles
- `<key>_characters.json` — character / voice assignments
- `<key>_EN_DUB.mp4` — final English dub
- `<key>_run.json` — run metadata

Cached processing is stored in:

```text
.anime_dubber_work/
```

Persistent series character data is stored in:

```text
.anime_dubber_series/
```

Do not delete the work cache for a long job unless you intentionally want to start over.

## Models / software

- MLX Whisper: `mlx-community/whisper-large-v3-turbo`
- Local translator: `mlx-community/Qwen3-4B-Instruct-2507-4bit`
- Demucs: `htdemucs`
- Optional speaker encoder: `speechbrain/spkrec-ecapa-voxceleb`
- Local TTS: macOS `say`
- Video/audio processing: FFmpeg
- YouTube retrieval: app-local yt-dlp

Model downloads happen on first use. After the models and source are cached, most of the local transcription, translation, and macOS TTS workflow can run locally.
