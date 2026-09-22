# Project workspace design and migration

## UX audit of the previous app

| Earlier location | Problem from a user's perspective | New location |
| --- | --- | --- |
| New Dub landing page: source, output folder, series, processing options | A second dub looks like a second project; source could change between runs | File → New Project owns the source. New Dub is only available inside an open project. |
| Projects table and inspector | One row per source, but each new run overwrote the visible last-run settings and rendered filename | Library lists projects; opening a project reveals Overview, Source / Media, Subtitles, Dubs, New Dub, Characters and Project Settings. |
| Project artifacts shown only after job completion | Subtitle-only users could not retrieve results until the entire dub completed | SRT and VTT are registered and emitted immediately after each stage writes them. The Subtitles screen exposes the files. |
| Global Characters table | Difficult to know which project a voice map belongs to | Characters sits inside the project workspace; each dub also snapshots its character map. |
| Settings and New Dub both contained provider choices | It was unclear which settings applied to a version | New Dub chooses version identity, language and provider; Settings holds provider defaults and credentials. Project Settings holds identity and processing defaults. |
| Activity was the main way to find files | Logs are useful for diagnosis but poor primary navigation | Files appear under Media, Subtitles and Dub Details; Activity remains available for diagnostics. |

The app uses SF Symbols consistently for the workspace navigation, file operations, processing, status and playback. System symbols inherit the macOS accent and adapt to light/dark appearance and display density.

## Data and output structure

A project identifies a source video in one output folder. Its manifest is `.anime_dubber_project/projects/<source-key>.json` (schema 2). `dubs` holds distinct version IDs, names, language, timestamps, settings, progress, errors, and output paths. `subtitles` holds each language and processing version separately. Versions write their translated SRT/VTT, dub video, dub audio and voice-map snapshot under `versions/<version-id>/`. The source transcription SRT/VTT and cached video are shared.

The pipeline emits the source transcript as soon as transcription finishes and the translated SRT/VTT as soon as translation finishes. The UI refreshes the project on each artifact event. A failed or cancelled TTS run therefore retains already written subtitle files. Output media and subtitle filenames do not overwrite earlier versions. Cached TTS and timeline signatures include the version so different voices cannot accidentally reuse another dub's audio.

Existing schema 1 manifests and older `*_run.json` outputs are presented as a legacy English version. Legacy outputs are left in place. Legacy versions have no isolated version folder, so Delete is disabled in the UI. The CLI continues to use the same backend and can register a project with `new-project`, list its versions with `projects`, or create more versions with `run`.

## Language and provider limits

The source-language pipeline currently assumes Mandarin (`zh`). English (`en`) supports the existing providers. Spanish, French, German and Japanese translations use MLX LLM or Ollama; Whisper direct translation only emits English. Non-English dubbing currently requires an ElevenLabs multilingual voice. Subtitle-only jobs do not require TTS. These constraints are checked before a job begins, and the New Dub screen explains them.

The Dub Details timing note describes the current timestamp fitting algorithm. It does not claim that lip sync has been measured visually or guarantee frame-perfect timing. Voice assignments are available in each dub's snapshotted character map. Media durations are saved once audio is probed.

## Verification

Run `python -m unittest discover -s tests -q` for backend tests. On macOS 14 or newer, build with `swift build --package-path macos/AnimeDubberApp` and exercise project creation, early subtitle availability, two versions of the same source, preview, export and deletion. A full model download / long-video timing review requires a machine with the installed ML providers and test media.
