# AI Anime English Dubber v3.5

A Mac-focused pipeline for turning Chinese AI animation / manhua-drama videos into English-subtitled or English-dubbed videos while retaining the original music and sound effects.

## v3.5 audio restoration update

v3.5 keeps all v3.4 timestamp/TTS robustness fixes and adds a hybrid soundtrack bed: the untouched original soundtrack is preserved outside dialogue, while the Demucs `no_vocals` stem is used only around detected speech with pre/post guards. It also trims TTS lead-in silence and turns aggressive background ducking off by default.

## What v3.5 includes

- Multi-character speaker detection / diarization.
- Persistent character voices across episodes when the same **Series ID** is used.
- Acoustic voice-type estimation for choosing a masculine/feminine/neutral English voice.
- Conservative **child / adult / older** voice classification.
- **Lead / major / supporting / minor** role assignment from speaking prominence.
- Per-line delivery detection: **normal / shouting / whispering**.
- Different macOS English voices for different characters when available.
- Character-specific speaking rate, pitch and gain.
- Style treatment: louder/more compressed shouting; quieter/breathier-filtered whispering.
- GUI Character / Voice Manager for manual corrections.
- CLI `analyze` command to inspect the cast before rendering a long dub.
- Optional SpeechBrain ECAPA speaker embeddings; automatic fallback to built-in acoustic clustering if ECAPA cannot load.

## Core pipeline

1. `yt-dlp` downloads a YouTube source, or a local video is used directly.
2. FFmpeg extracts the soundtrack.
3. Demucs separates the dialogue/vocal stem from the music + SFX stem.
4. MLX-Whisper transcribes Mandarin.
5. A local MLX LLM translates the transcript into concise English while preserving xianxia terminology.
6. v3.3 analyzes each spoken segment and clusters recurring speakers.
7. Each speaker receives a persistent character profile and English voice.
8. Each line is classified as normal, shouting, or whispering.
9. English speech is synthesized, adjusted to fit the original timing, and placed on the original timeline.
10. The new English dialogue is mixed over the preserved music/SFX and muxed back into the original video.

## Accuracy notes

Speaker diarization is inherently imperfect in anime because voices can overlap with music, effects, shouting and transformations. ECAPA gives the best automatic speaker matching in this build. The built-in acoustic fallback works without an extra model but is less reliable.

The voice-type and age categories are conservative acoustic estimates used only to choose TTS voices. They are not identity claims. A high-pitched adult character can be mistaken for a child and a rough low voice can be mistaken for an older character. Use **Analyze characters first** and the Character Manager for important long-form jobs.

`lead/major/supporting/minor` is based on speaking share, not complete plot understanding. In a narrator-heavy series, you may want to manually change the role.

## First install on macOS

Because the scripts are generated rather than Apple-signed/notarized, Finder may initially show a Gatekeeper warning. Use Terminal for the first setup:

```bash
cd /path/to/AnimeDubberMac-v3.3
/bin/zsh setup.sh
```

The setup script explicitly removes the quarantine attribute from **this extracted app folder only** after you chose to run it, so `Run GUI.command` can normally be opened afterward.

## GUI

After setup:

```bash
.venv/bin/python -m anime_dubber.gui
```

For the linked Season 2 compilation, the GUI is pre-filled with:

```text
https://youtu.be/WH9x3hYwPj0
```

Recommended settings:

- Translation: **Local LLM**
- Character dubbing: **On**
- Speaker backend: **auto**
- Series ID: **10000-years-cultivation**
- TTS: **macOS local/free**
- Background ducking: **Off**

Use **Analyze characters first** before rendering the full compilation. The character map is saved as `<video-key>_characters.json` and can be edited from the GUI.

## CLI examples

Analyze the cast first:

```bash
./anime-dubber analyze "https://youtu.be/WH9x3hYwPj0" \
  --series-id 10000-years-cultivation
```

Generate the full local multi-character dub:

```bash
./anime-dubber run "https://youtu.be/WH9x3hYwPj0" \
  --series-id 10000-years-cultivation \
  --translation llm \
  --tts macos
```

Force the built-in offline speaker clustering instead of ECAPA:

```bash
./anime-dubber run VIDEO.mp4 --speaker-backend acoustic
```

System check:

```bash
./anime-dubber doctor
```

List installed English macOS voices:

```bash
./anime-dubber voices
```

## Files produced

Typical output:

- `<key>_zh.srt` — Mandarin transcript
- `<key>_en.srt` — English subtitles
- `<key>_characters.json` — detected characters, voice assignments and style statistics
- `<key>_EN_DUB.mp4` — final English dub with original music/SFX
- `<key>_run.json` — processing settings/model metadata

Internal cached work is stored under `.anime_dubber_work/`. Series voice identities are stored under `.anime_dubber_series/`.

## Local vs ElevenLabs

The fully automatic multi-character path is designed around **macOS local voices** because they can be assigned automatically without cost. ElevenLabs remains available, but a single default ElevenLabs voice ID is used unless you add character-specific `elevenlabs_voice_id` values to the character map. This avoids silently spending credits across a long multi-hour compilation.

## Models / software

- MLX Whisper: `mlx-community/whisper-large-v3-turbo`
- Local translator: `mlx-community/Qwen3-4B-Instruct-2507-4bit`
- Demucs: `htdemucs`
- Optional speaker encoder: `speechbrain/spkrec-ecapa-voxceleb`
- TTS: macOS `say` by default

Model downloads happen on first use. YouTube retrieval also requires internet; after the models and source are cached, the MLX translation/TTS path is local.


## v3.3 reliability change

v3.3 adds a standard-library-only `verify_source.py` preflight. `setup.sh` runs it immediately after Homebrew Python is available and **before** installing ML dependencies, then runs it again after installation. The release build is also tested from a fresh extraction of the final ZIP. A regression test now renders an FFmpeg concat timeline inside a path containing an apostrophe, covering the quoting bug that broke v3.


## YouTube 403 / SABR handling (v3.3)

v3.3 no longer calls whichever `yt-dlp` happens to be first on your Mac's PATH.
It installs and uses an **app-local yt-dlp** through the virtual environment.

For YouTube sources it automatically tries:
1. normal 1080p download,
2. the `web_embedded` YouTube client,
3. HLS/web-embedded fallback formats (including 91–96 and format 18).

It also forces IPv4. This is intended to handle current YouTube SABR/403 changes
without requiring you to know yt-dlp flags.

If all automatic attempts fail, use a local video file as the input. The app
does not silently read browser cookies.


## Real YouTube download progress (v3.3)

During YouTube downloads the GUI switches from the generic spinner to a
determinate progress bar showing percentage, speed, ETA, and the current
fallback attempt. Once download is finished it switches back to the stage
spinner for ML steps that do not expose a reliable percentage.

The CLI shows the same download information on one updating line.
