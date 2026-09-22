# AnimeDubber SwiftUI Redesign Specification

Status: design-first proposal  
Target: v4 architecture  
Frontend: native SwiftUI on macOS  
Backend: Python pipeline service  
CLI: Python, cross-platform for macOS / Windows / Linux

---

## 1. Product goal

AnimeDubber should feel like a real macOS application, not a developer form wrapped in a window.

The redesign must:

- stay clean at first launch;
- remain usable when new providers, models, and processing options are added later;
- separate common controls from advanced controls;
- show progress as structured job state instead of dumping raw logs into the main workflow;
- preserve the current Python processing code and cache format where practical;
- support a native SwiftUI macOS frontend;
- retain a Python CLI for headless use and for Windows / Linux users;
- make the SwiftUI app and CLI use the same backend/service layer so behavior does not diverge.

---

## 2. Design principles

### Native over custom

Use SwiftUI native controls, system materials, SF Symbols, standard spacing, and system colors. Avoid hardcoded white cards, imitation macOS controls, or excessive borders.

### Progressive disclosure

The default screen shows only the settings needed for a normal dub. Advanced speaker thresholds, model overrides, cache controls, and diagnostic settings live in an inspector or disclosure groups.

### Workflow first

The user thinks in terms of:

1. choose source;
2. choose project/series;
3. choose how the dub should be produced;
4. optionally review characters;
5. run;
6. inspect output.

The UI should mirror that mental model.

### Structured progress

The app should expose stages such as Downloading, Extracting Audio, Separating Stems, Transcribing, Translating, Analyzing Characters, Synthesizing Speech, Mixing, and Exporting.

A raw log remains available for diagnostics, but it is not the primary status UI.

### Expand without redesign

New TTS providers, translation engines, or speaker models should be added as provider rows / settings panels, not by adding more controls to one giant form.

---

## 3. Main information architecture

Use a native macOS `NavigationSplitView`.

Sidebar destinations:

- New Dub
- Projects
- Characters
- Activity
- Settings

The sidebar is always visible at normal desktop widths and can collapse automatically on smaller widths.

A toolbar contains:

- current backend connection state;
- System Check;
- optional Inspector toggle;
- app-level Settings shortcut if desired.

The app window should default to approximately 1180 x 780 and support resizing down to roughly 940 x 650 without controls overlapping.

---

## 4. Main screen wireframes

### 4.1 New Dub

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ AnimeDubber                                             ● Backend Ready   ⚙︎ │
├───────────────┬─────────────────────────────────────────────────────────────┤
│ New Dub       │ New Dub                                                     │
│ Projects      │ Create an English dub while preserving music and effects.  │
│ Characters    │                                                             │
│ Activity      │ ┌─────────────────────────────────────────────────────────┐ │
│ Settings      │ │ SOURCE                                                  │ │
│               │ │ [ YouTube URL or local video                         ] │ │
│               │ │ [ Choose File ]                                         │ │
│               │ └─────────────────────────────────────────────────────────┘ │
│               │                                                             │
│               │ ┌─────────────────────────────────────────────────────────┐ │
│               │ │ PROJECT                                                 │ │
│               │ │ Series ID      [ 10000-years-cultivation              ] │ │
│               │ │ Output folder  [ ~/Movies/AnimeDubber                ] │ │
│               │ │ Resume cached work  [on]                                │ │
│               │ └─────────────────────────────────────────────────────────┘ │
│               │                                                             │
│               │ ┌─────────────────────────────────────────────────────────┐ │
│               │ │ PIPELINE                                                │ │
│               │ │ Output       English dub + subtitles  ▾                 │ │
│               │ │ Translation  Local LLM                  ▾                │ │
│               │ │ Voices       macOS Local                ▾                │ │
│               │ │ Characters   Detect separate speakers   [on]             │ │
│               │ │                                              [Advanced] │ │
│               │ └─────────────────────────────────────────────────────────┘ │
│               │                                                             │
│               │                    [ Analyze Characters ] [ Generate Dub ]   │
├───────────────┴─────────────────────────────────────────────────────────────┤
│ Ready                                                        Activity  ˄    │
└─────────────────────────────────────────────────────────────────────────────┘
```

Design notes:

- Source is the first visual focus.
- Project settings are compact.
- Common pipeline choices are summary rows with popovers/pickers.
- Advanced settings are hidden by default.
- Generate Dub is the only prominent primary button.
- Analyze Characters is secondary.
- The bottom status strip is always visible.
- The Activity drawer is collapsed by default.

### 4.2 Advanced inspector

The inspector appears on the right only when requested.

```text
┌──────────────────────────────┐
│ Advanced                     │
│                              │
│ Speaker backend              │
│ Auto                     ▾   │
│                              │
│ Maximum speakers             │
│ 12                           │
│                              │
│ Speaker threshold            │
│ Automatic                    │
│                              │
│ Series context               │
│ [ multiline context... ]     │
│                              │
│ Audio                        │
│ Music / SFX          1.00    │
│ English voice       1.15     │
│ Background ducking   Off     │
└──────────────────────────────┘
```

This prevents the normal workflow from becoming crowded as features grow.

### 4.3 Projects

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Projects                                                Search       │
│                                                                      │
│ 10000 Years Cultivation                         Completed            │
│ WH9x3hYwPj0 · 2h 31m                            Sep 22               │
│ [ Open Output ] [ Re-run ] [ Show Details ]                          │
│ ──────────────────────────────────────────────────────────────────── │
│ Episode 04                                       Interrupted          │
│ local_video_04.mp4                               Sep 20               │
│ [ Resume ] [ Show Details ]                                          │
└──────────────────────────────────────────────────────────────────────┘
```

A project detail view shows:

- source;
- output artifacts;
- configuration snapshot;
- characters used;
- processing history;
- cache location;
- Resume / Re-run / Reveal in Finder actions.

### 4.4 Characters

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ Characters                                     Search   Filter ▾           │
│                                                                            │
│ Character      Role        Voice       Lines      Confidence               │
│ Character 01   Lead        Daniel      413        High                     │
│ Character 02   Major       Samantha    286        Medium                   │
│ Character 03   Supporting  Alex        144        High                     │
│                                                                            │
│                                             ┌────────────────────────────┐ │
│                                             │ Character 01               │ │
│                                             │ Display name [ ......... ] │ │
│                                             │ Role         Lead       ▾  │ │
│                                             │ Voice        Daniel     ▾  │ │
│                                             │ Rate         205           │ │
│                                             │ Pitch        0.0           │ │
│                                             │ Gain         1.0           │ │
│                                             │ [ Preview ] [ Save ]       │ │
│                                             └────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────┘
```

Use a SwiftUI `Table` on macOS. Selecting a character opens a detail inspector. No separate old-style modal is required for common editing.

### 4.5 Activity

Activity is structured, searchable, and useful.

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ Activity                                      Job: WH9x3hYwPj0 ▾          │
│                                                                            │
│ ✓ Download source                     100%     00:42                       │
│ ✓ Extract soundtrack                  100%     00:08                       │
│ ✓ Separate dialogue / music           100%     12:31                       │
│ ● Transcribe Mandarin                  63%     18:04                       │
│ ○ Translate to English                                                     │
│ ○ Analyze characters                                                       │
│ ○ Synthesize English speech                                                │
│ ○ Mix and export                                                           │
│                                                                            │
│ [ Diagnostics ] [ Warnings 2 ] [ Output Files ]                            │
└────────────────────────────────────────────────────────────────────────────┘
```

Diagnostics contains the raw multiline backend log with:

- real line breaks;
- monospaced font;
- timestamps;
- copy;
- clear;
- save/export;
- follow-tail toggle;
- horizontal wrapping optional.

### 4.6 Settings

Settings sections:

- General
- Models
- Providers
- Storage
- Backend
- Advanced

API keys are stored in macOS Keychain, never in plaintext user defaults.

Storage shows cache size and allows the user to clear selected project caches without deleting all work.

---

## 5. Job states and user feedback

Every long-running operation is represented by a job.

Job states:

```text
queued
preparing
downloading
extracting_audio
separating_stems
transcribing
translating
analyzing_characters
synthesizing
mixing
exporting
completed
failed
cancelled
```

Each stage supports:

- title;
- optional determinate progress from 0 to 1;
- short human-readable detail;
- elapsed time;
- warnings;
- current item count when meaningful.

The UI should never fake a percentage for a stage that does not expose one. Use an indeterminate progress indicator for those stages.

---

## 6. SwiftUI frontend architecture

Suggested repository location:

```text
macos/
  AnimeDubber/
    AnimeDubber.xcodeproj
    AnimeDubber/
      AnimeDubberApp.swift
      AppState.swift

      Models/
        AppProject.swift
        BackendMessage.swift
        CharacterProfile.swift
        Job.swift
        JobStage.swift
        Provider.swift

      Services/
        BackendClient.swift
        BackendProcess.swift
        KeychainStore.swift
        ProjectStore.swift

      Views/
        Sidebar/
          SidebarView.swift

        NewDub/
          NewDubView.swift
          SourceSection.swift
          ProjectSection.swift
          PipelineSection.swift
          AdvancedInspector.swift

        Projects/
          ProjectsView.swift
          ProjectDetailView.swift

        Characters/
          CharactersView.swift
          CharacterInspector.swift

        Activity/
          ActivityView.swift
          DiagnosticsView.swift
          ArtifactsView.swift

        Settings/
          SettingsView.swift

        Shared/
          StatusBar.swift
          EmptyStateView.swift
          ProviderPicker.swift
          SectionCard.swift
```

Use:

- `NavigationSplitView`;
- `Table`;
- `Inspector`;
- `DisclosureGroup`;
- `ProgressView`;
- native sheets and alerts;
- system colors and materials;
- SF Symbols;
- `@Observable` / Observation where deployment target allows it.

Avoid custom-drawn buttons unless a native component cannot express the desired behavior.

---

## 7. Python backend architecture

The Python code becomes the single source of truth for processing.

Suggested structure:

```text
anime_dubber/
  __init__.py

  application/
    service.py
    jobs.py
    events.py
    project.py

  pipeline/
    core.py
    audio.py
    transcription.py
    translation.py
    speakers.py
    tts.py
    mixing.py

  providers/
    asr/
      mlx_whisper.py
      faster_whisper.py

    translation/
      mlx_llm.py
      whisper_translate.py
      ollama.py

    tts/
      macos_say.py
      piper.py
      elevenlabs.py

  transport/
    stdio_server.py
    protocol.py

  cli.py
```

The current pipeline can be migrated gradually rather than rewritten all at once.

The key rule is:

```text
SwiftUI ─┐
         ├──> Application Service ──> Pipeline / Providers
CLI ─────┘
```

SwiftUI must not call low-level pipeline functions directly.

The CLI must not implement its own separate processing behavior.

---

## 8. Swift ↔ Python communication

For the macOS app, launch the Python backend as a local child process.

During development:

```text
.venv/bin/python -m anime_dubber.transport.stdio_server
```

The Swift app communicates through stdin/stdout using newline-delimited JSON.

This avoids:

- opening a localhost network port;
- firewall prompts;
- port conflicts;
- unnecessary HTTP server complexity.

### Request example

```json
{"type":"request","id":"42","method":"run_job","params":{"source":"https://youtu.be/...","output_dir":"/Users/...","series_id":"..."}}
```

### Response example

```json
{"type":"response","id":"42","ok":true,"result":{"job_id":"job_123"}}
```

### Event examples

```json
{"type":"event","job_id":"job_123","event":"stage","data":{"stage":"transcribing","title":"Transcribing Mandarin"}}
{"type":"event","job_id":"job_123","event":"progress","data":{"fraction":0.63,"completed":1712,"total":2717}}
{"type":"event","job_id":"job_123","event":"log","data":{"level":"info","message":"Loaded cached transcript"}}
{"type":"event","job_id":"job_123","event":"warning","data":{"code":"SHORT_SEGMENT_REPAIRED","message":"Repaired 14 malformed timestamp segments"}}
{"type":"event","job_id":"job_123","event":"artifact","data":{"kind":"video","path":"/Users/.../episode_EN_DUB.mp4"}}
{"type":"event","job_id":"job_123","event":"finished","data":{"status":"completed"}}
```

Requests to support initially:

```text
hello
system_check
capabilities
list_voices
list_models
analyze_characters
run_job
cancel_job
get_job
get_project
clear_project_cache
shutdown
```

---

## 9. Cross-platform CLI

The CLI returns as a first-class interface.

Command shape:

```bash
animedubber doctor
animedubber analyze SOURCE --series-id my-series
animedubber run SOURCE --output ./output --series-id my-series
animedubber characters SOURCE
animedubber cache list
animedubber cache clear JOB_ID
```

The CLI uses the same `ApplicationService` used by the SwiftUI backend process.

### Platform provider strategy

macOS Apple silicon:

- ASR: MLX Whisper
- Translation: MLX local LLM
- TTS: macOS say
- Stem separation: Demucs
- Optional: ElevenLabs

Windows / Linux:

- ASR: Faster-Whisper
- Translation default: Whisper direct translation or an optional Ollama provider
- TTS: Piper or ElevenLabs
- Stem separation: Demucs with CPU/CUDA

The CLI performs capability detection instead of assuming every backend exists.

Example:

```text
$ animedubber doctor

Platform: Windows 11
ASR
  ✓ faster-whisper
  - mlx-whisper unavailable on this platform

Translation
  ✓ Whisper direct translation
  ✓ Ollama detected
  - MLX local LLM unavailable on this platform

TTS
  ✓ Piper
  ✓ ElevenLabs configured
  - macOS voices unavailable
```

This means Windows / Linux users still receive a real usable CLI rather than a CLI that only exposes macOS-specific providers.

---

## 10. Configuration model

Create one versioned project configuration schema shared by SwiftUI and CLI.

Example:

```json
{
  "schema_version": 1,
  "source": "https://youtu.be/...",
  "output_dir": "/Users/me/Movies/AnimeDubber",
  "series_id": "10000-years-cultivation",
  "mode": "dub",
  "translation": {
    "provider": "mlx_llm"
  },
  "asr": {
    "provider": "mlx_whisper"
  },
  "speaker_analysis": {
    "enabled": true,
    "backend": "auto",
    "max_speakers": 12,
    "threshold": null
  },
  "tts": {
    "provider": "macos",
    "fallback_voice": "",
    "rate": 210
  },
  "audio": {
    "background_volume": 1.0,
    "dub_volume": 1.15,
    "ducking": false
  },
  "resume": true
}
```

SwiftUI edits this model. CLI flags override the same model.

---

## 11. Project persistence

Each job should write a lightweight manifest in the output workspace:

```text
.anime_dubber_project/
  project.json
  jobs/
    job_123.json
  logs/
    job_123.log
```

Heavy intermediates remain in the existing work cache.

The project manifest should contain:

- source;
- title;
- duration;
- current status;
- selected configuration;
- artifacts;
- timestamps;
- character-map reference;
- warnings;
- backend version.

This powers the Projects screen without rescanning huge cache directories.

---

## 12. Logging redesign

The Python backend should emit structured events and also write a normal log file.

Each log record should have:

```text
timestamp
job_id
level
stage
message
optional metadata
```

Human-readable file example:

```text
2026-09-22 02:42:10 INFO  transcribing  Loaded cached transcript: 2717 segments
2026-09-22 02:42:11 WARN  transcribing  Repaired 94 invalid timestamp ranges
2026-09-22 02:43:20 INFO  tts           Synthesized 1200/2717 clips
```

The SwiftUI Diagnostics view should render each record as a separate line. Multiline backend messages should remain multiline rather than showing literal `\n` text.

---

## 13. Error UX

Errors should have three layers:

1. short user-facing explanation;
2. recommended action;
3. expandable technical details.

Example:

```text
English speech could not be generated for one segment.

AnimeDubber retried the clip but the generated audio was empty.
The job can continue by skipping the line or you can retry it.

[ Retry Segment ] [ Skip and Continue ]

Technical Details ▸
```

Do not show a Python stack trace as the primary alert.

---

## 14. Responsive behavior

Wide window:

```text
sidebar | main workflow | optional inspector
```

Medium window:

```text
sidebar | main workflow
inspector opens as overlay
```

Smallest supported window:

```text
collapsible sidebar
single-column workflow
bottom Activity drawer
```

Avoid fixed pixel widths for the entire form.

Use flexible frames, min/max widths, and SwiftUI's adaptive layout tools.

---

## 15. Packaging plan

### Development

SwiftUI launches:

```text
<repo>/.venv/bin/python -m anime_dubber.transport.stdio_server
```

This keeps development simple while the backend is changing rapidly.

### Release

Do not make the final user manually install Python.

The preferred release packaging path is to bundle a controlled Python runtime and backend resources inside the macOS app bundle, or ship a backend helper executable if the ML dependencies can be packaged reliably.

Because MLX, PyTorch / Demucs, and model dependencies are large, packaging should be treated as its own milestone after the UI/backend protocol is stable.

Models remain external downloads/cache rather than being embedded into the app bundle.

---

## 16. Implementation sequence

### Phase 1 — backend boundary

- restore a CLI;
- introduce `ApplicationService`;
- introduce structured job events;
- keep current core pipeline underneath;
- add JSONL stdio transport;
- add protocol tests.

No SwiftUI yet.

### Phase 2 — SwiftUI shell

- create Xcode project;
- implement sidebar and destinations;
- implement backend process connection;
- show backend readiness / system check;
- create New Dub screen using mock data first.

### Phase 3 — real New Dub workflow

- bind SwiftUI configuration to backend schema;
- implement Analyze Characters;
- implement Generate Dub;
- implement cancellation;
- implement structured progress and Activity drawer.

### Phase 4 — project and character management

- Projects screen;
- Character table and inspector;
- voice preview;
- artifact opening / Reveal in Finder;
- project persistence.

### Phase 5 — cross-platform CLI providers

- Faster-Whisper;
- Piper;
- optional Ollama;
- platform-aware doctor command;
- Windows and Linux tests.

### Phase 6 — packaging and polish

- Keychain integration;
- keyboard shortcuts;
- menu commands;
- accessibility labels;
- dark mode review;
- app icon;
- bundled backend strategy;
- signed/notarized macOS release.

---

## 17. Testing plan

Python:

- pipeline unit tests;
- timestamp sanitizer regression tests;
- TTS empty-audio regression tests;
- soundtrack-bed tests;
- protocol encode/decode tests;
- cancellation tests;
- application-service tests;
- CLI parser tests;
- capability detection tests.

Swift:

- BackendMessage decoding tests;
- job-state reducer tests;
- project persistence tests;
- view-model tests;
- basic UI navigation tests.

End-to-end:

- short local fixture;
- cached resume;
- cancellation;
- failed TTS segment;
- malformed Whisper timing;
- mixed soundtrack preservation;
- character analysis;
- final artifact registration.

CI:

- macOS: Swift build + Python unit tests;
- Ubuntu: Python CLI tests;
- Windows: Python CLI tests;
- heavy ML integration jobs remain optional/manual because of runtime and model size.

---

## 18. Acceptance criteria before implementation is considered complete

The redesign is complete when:

- the normal New Dub screen does not expose expert-only controls by default;
- the window can resize without clipped or overlapping controls;
- dark and light mode both look native;
- SwiftUI can start and stop Python jobs without a network server;
- progress is stage-based and structured;
- diagnostics preserve multiline logs correctly;
- Character Voices are editable in a native table/inspector layout;
- existing v3.4 timestamp reliability fixes remain;
- existing v3.5 soundtrack restoration behavior remains;
- the same processing service powers both SwiftUI and CLI;
- the CLI runs on macOS, Windows, and Linux with platform-appropriate providers;
- no API keys are stored in plaintext;
- existing cached projects remain resumable where compatible.

---

## 19. Decision for the current repository

Do not continue polishing the Tkinter interface.

Keep it only temporarily while the backend boundary is created. Once the SwiftUI New Dub workflow reaches feature parity, remove the Tkinter frontend.

The Python CLI should be restored and retained permanently.
