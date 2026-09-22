import AppKit
import Foundation
import SwiftUI
import UniformTypeIdentifiers

@MainActor
final class AppState: ObservableObject {
    @Published var selection: SidebarDestination? = .newDub

    @Published var source = "https://youtu.be/WH9x3hYwPj0"
    @Published var outputFolder = "~/Movies/AnimeDubber"
    @Published var seriesID = "10000-years-cultivation"
    @Published var outputMode: OutputMode = .dub

    @Published var asrProvider: ASRProvider = .auto
    @Published var fasterWhisperModel = "large-v3"
    @Published var fasterWhisperDevice = "auto"
    @Published var fasterWhisperComputeType = "auto"

    @Published var translationProvider: TranslationProvider = .llm
    @Published var ollamaURL = "http://127.0.0.1:11434"
    @Published var ollamaModel = "qwen3:4b"

    @Published var voiceProvider: VoiceProvider = .auto
    @Published var fallbackVoice = ""
    @Published var ttsRate = 210
    @Published var chatterboxReferenceAudio = ""
    @Published var chatterboxExpressiveness = 0.5
    @Published var chatterboxDevice = "auto"
    @Published var chatterboxTurbo = true
    @Published var kokoroVoice = "auto"
    @Published var piperModel = ""
    @Published var piperSpeaker = -1
    @Published var elevenLabsVoiceID = "JBFqnCBsd6RMkjVDRZzb"
    @Published var elevenLabsAPIKey = ""
    @Published var credentialStatus = ""

    @Published var detectCharacters = true
    @Published var resumeCachedWork = true
    @Published var speakerBackend = "auto"
    @Published var maxSpeakers = 12
    @Published var speakerThreshold = 0.0
    @Published var seriesContext = "Chinese xianxia/xuanhuan cultivation animation. Keep names, sects, realms, system terms, and cultivation terminology consistent."
    @Published var backgroundVolume = 1.0
    @Published var dubVolume = 1.15
    @Published var backgroundDucking = false

    @Published var backendState: BackendConnectionState = .connecting
    @Published var backendDiagnostics = ""
    @Published var activity: [ActivityEntry] = []
    @Published var activityExpanded = false
    @Published var statusText = "Connecting to backend…"
    @Published var progressFraction: Double?
    @Published var activeJobID: String?
    @Published var systemCheckItems: [SystemCheckItem] = []
    @Published var showingSystemCheck = false

    @Published var projects: [ProjectSummary] = []
    @Published var selectedProjectID: String?

    @Published var characterMaps: [CharacterMapSummary] = []
    @Published var selectedCharacterMapPath: String?
    @Published var characters: [CharacterItem] = []
    @Published var selectedCharacterID: String?
    @Published var characterDraft = CharacterDraft()
    @Published var installedVoices: [String] = []
    @Published var characterSaveMessage = ""

    private let backend = BackendProcess()

    init() {
        loadPreferences()
        elevenLabsAPIKey = KeychainStore.string(for: "elevenlabs-api-key") ?? ""
        connectBackend()
    }

    deinit {
        backend.stop()
    }

    var canStartJob: Bool {
        guard case .ready = backendState else { return false }
        return !source.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && activeJobID == nil
    }

    var settingsSnapshot: SettingsSnapshot {
        SettingsSnapshot(
            outputFolder: outputFolder,
            seriesID: seriesID,
            outputMode: outputMode,
            asrProvider: asrProvider,
            fasterWhisperModel: fasterWhisperModel,
            fasterWhisperDevice: fasterWhisperDevice,
            fasterWhisperComputeType: fasterWhisperComputeType,
            translationProvider: translationProvider,
            ollamaURL: ollamaURL,
            ollamaModel: ollamaModel,
            voiceProvider: voiceProvider,
            fallbackVoice: fallbackVoice,
            ttsRate: ttsRate,
            chatterboxReferenceAudio: chatterboxReferenceAudio,
            chatterboxExpressiveness: chatterboxExpressiveness,
            chatterboxDevice: chatterboxDevice,
            chatterboxTurbo: chatterboxTurbo,
            kokoroVoice: kokoroVoice,
            piperModel: piperModel,
            piperSpeaker: piperSpeaker,
            elevenLabsVoiceID: elevenLabsVoiceID,
            detectCharacters: detectCharacters,
            resumeCachedWork: resumeCachedWork,
            speakerBackend: speakerBackend,
            maxSpeakers: maxSpeakers,
            speakerThreshold: speakerThreshold,
            seriesContext: seriesContext,
            backgroundVolume: backgroundVolume,
            dubVolume: dubVolume,
            backgroundDucking: backgroundDucking
        )
    }

    func savePreferences() {
        AppPreferences(
            outputFolder: outputFolder,
            seriesID: seriesID,
            outputMode: outputMode.rawValue,
            asrProvider: asrProvider.rawValue,
            fasterWhisperModel: fasterWhisperModel,
            fasterWhisperDevice: fasterWhisperDevice,
            fasterWhisperComputeType: fasterWhisperComputeType,
            translationProvider: translationProvider.rawValue,
            ollamaURL: ollamaURL,
            ollamaModel: ollamaModel,
            voiceProvider: voiceProvider.rawValue,
            fallbackVoice: fallbackVoice,
            ttsRate: ttsRate,
            chatterboxReferenceAudio: chatterboxReferenceAudio,
            chatterboxExpressiveness: chatterboxExpressiveness,
            chatterboxDevice: chatterboxDevice,
            chatterboxTurbo: chatterboxTurbo,
            kokoroVoice: kokoroVoice,
            piperModel: piperModel,
            piperSpeaker: piperSpeaker,
            elevenLabsVoiceID: elevenLabsVoiceID,
            detectCharacters: detectCharacters,
            resumeCachedWork: resumeCachedWork,
            speakerBackend: speakerBackend,
            maxSpeakers: maxSpeakers,
            speakerThreshold: speakerThreshold,
            seriesContext: seriesContext,
            backgroundVolume: backgroundVolume,
            dubVolume: dubVolume,
            backgroundDucking: backgroundDucking
        ).save()
    }

    func saveSecrets() {
        do {
            let trimmed = elevenLabsAPIKey.trimmingCharacters(in: .whitespacesAndNewlines)
            if trimmed.isEmpty {
                try KeychainStore.delete("elevenlabs-api-key")
                credentialStatus = "API key removed from Keychain."
            } else {
                try KeychainStore.set(trimmed, for: "elevenlabs-api-key")
                credentialStatus = "API key saved securely in Keychain."
            }
        } catch {
            credentialStatus = error.localizedDescription
        }
    }

    private func loadPreferences() {
        let preferences = AppPreferences.load()

        outputFolder = preferences.outputFolder
        seriesID = preferences.seriesID
        outputMode = OutputMode(rawValue: preferences.outputMode) ?? .dub
        asrProvider = ASRProvider(rawValue: preferences.asrProvider) ?? .auto
        fasterWhisperModel = preferences.fasterWhisperModel
        fasterWhisperDevice = preferences.fasterWhisperDevice
        fasterWhisperComputeType = preferences.fasterWhisperComputeType
        translationProvider = TranslationProvider(rawValue: preferences.translationProvider) ?? .llm
        ollamaURL = preferences.ollamaURL
        ollamaModel = preferences.ollamaModel
        voiceProvider = VoiceProvider(rawValue: preferences.voiceProvider) ?? .auto
        fallbackVoice = preferences.fallbackVoice
        ttsRate = preferences.ttsRate
        chatterboxReferenceAudio = preferences.chatterboxReferenceAudio
        chatterboxExpressiveness = preferences.chatterboxExpressiveness
        chatterboxDevice = preferences.chatterboxDevice
        chatterboxTurbo = preferences.chatterboxTurbo
        kokoroVoice = preferences.kokoroVoice
        piperModel = preferences.piperModel
        piperSpeaker = preferences.piperSpeaker
        elevenLabsVoiceID = preferences.elevenLabsVoiceID
        detectCharacters = preferences.detectCharacters
        resumeCachedWork = preferences.resumeCachedWork
        speakerBackend = preferences.speakerBackend
        maxSpeakers = preferences.maxSpeakers
        speakerThreshold = preferences.speakerThreshold
        seriesContext = preferences.seriesContext
        backgroundVolume = preferences.backgroundVolume
        dubVolume = preferences.dubVolume
        backgroundDucking = preferences.backgroundDucking
    }

    func connectBackend() {
        backendState = .connecting
        statusText = "Connecting to backend…"

        do {
            try backend.start(
                onMessage: { [weak self] payload in
                    Task { @MainActor in
                        self?.handleBackendMessage(payload)
                    }
                },
                onDiagnostic: { [weak self] text in
                    Task { @MainActor in
                        self?.backendDiagnostics += text
                    }
                },
                onTermination: { [weak self] code in
                    Task { @MainActor in
                        guard let self else { return }
                        if self.activeJobID != nil {
                            self.activity.append(ActivityEntry(kind: .error, message: "Backend exited with code \(code)."))
                        }
                        self.activeJobID = nil
                        self.backendState = .disconnected
                        self.statusText = "Backend offline"
                    }
                }
            )

            _ = try backend.send(method: "hello", id: "hello")
            _ = try backend.send(method: "capabilities", id: "capabilities")
        } catch {
            backendState = .failed(error.localizedDescription)
            statusText = error.localizedDescription
            activity.append(ActivityEntry(kind: .error, message: error.localizedDescription))
        }
    }

    func runSystemCheck() {
        do {
            _ = try backend.send(method: "system_check", id: "system-check")
        } catch {
            systemCheckItems = [SystemCheckItem(name: "Backend", ok: false, detail: error.localizedDescription)]
            showingSystemCheck = true
        }
    }

    func startJob(analysis: Bool) {
        guard canStartJob else { return }

        savePreferences()
        let threshold: Any = speakerThreshold == 0 ? NSNull() : speakerThreshold

        let params: [String: Any] = [
            "source": source,
            "output_dir": outputFolder,
            "series_id": seriesID,
            "mode": outputMode.rawValue,
            "asr": [
                "provider": asrProvider.rawValue,
                "model": fasterWhisperModel,
                "device": fasterWhisperDevice,
                "compute_type": fasterWhisperComputeType,
            ],
            "translation": [
                "provider": translationProvider.rawValue,
                "ollama_url": ollamaURL,
                "model": ollamaModel,
            ],
            "tts": [
                "provider": voiceProvider.rawValue,
                "fallback_voice": fallbackVoice,
                "rate": ttsRate,
                "chatterbox_reference_audio": chatterboxReferenceAudio,
                "chatterbox_expressiveness": chatterboxExpressiveness,
                "chatterbox_device": chatterboxDevice,
                "chatterbox_turbo": chatterboxTurbo,
                "kokoro_voice": kokoroVoice,
                "piper_model": piperModel,
                "piper_speaker": piperSpeaker,
                "api_key": elevenLabsAPIKey,
                "voice_id": elevenLabsVoiceID,
            ],
            "speaker_analysis": [
                "enabled": detectCharacters,
                "backend": speakerBackend,
                "max_speakers": maxSpeakers,
                "threshold": threshold,
            ],
            "audio": [
                "background_volume": backgroundVolume,
                "dub_volume": dubVolume,
                "ducking": backgroundDucking,
            ],
            "context": seriesContext,
            "resume": resumeCachedWork,
        ]

        do {
            statusText = analysis ? "Starting character analysis…" : "Starting dub…"
            progressFraction = nil
            activityExpanded = true
            let id = analysis ? "analyze-\(UUID().uuidString)" : "run-\(UUID().uuidString)"
            _ = try backend.send(
                method: analysis ? "analyze_characters" : "run_job",
                params: params,
                id: id
            )
        } catch {
            activity.append(ActivityEntry(kind: .error, message: error.localizedDescription))
            statusText = "Could not start"
        }
    }

    func cancelActiveJob() {
        guard let activeJobID else { return }
        do {
            _ = try backend.send(
                method: "cancel_job",
                params: ["job_id": activeJobID],
                id: "cancel-\(UUID().uuidString)"
            )
            statusText = "Cancelling…"
        } catch {
            activity.append(ActivityEntry(kind: .error, message: error.localizedDescription))
        }
    }

    func refreshProjects() {
        do {
            _ = try backend.send(
                method: "list_projects",
                params: ["output_dir": outputFolder],
                id: "projects-\(UUID().uuidString)"
            )
        } catch {
            activity.append(ActivityEntry(kind: .error, message: error.localizedDescription))
        }
    }

    func useProject(_ project: ProjectSummary) {
        source = project.source
        outputFolder = project.outputDir
        seriesID = project.seriesID
        selection = .newDub
    }

    func openProjectOutput(_ project: ProjectSummary) {
        let preferred = project.artifacts["dubbed_video"]
            ?? project.artifacts["english_srt"]
            ?? project.artifacts.values.first
        guard let preferred, !preferred.isEmpty else { return }
        NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: preferred)])
    }

    func refreshCharacterMaps() {
        do {
            _ = try backend.send(
                method: "list_character_maps",
                params: ["output_dir": outputFolder],
                id: "character-maps-\(UUID().uuidString)"
            )
        } catch {
            activity.append(ActivityEntry(kind: .error, message: error.localizedDescription))
        }
    }

    func loadCharacterMap(_ path: String) {
        guard !path.isEmpty else { return }
        selectedCharacterMapPath = path
        selectedCharacterID = nil
        characters = []
        characterDraft = CharacterDraft()
        do {
            _ = try backend.send(
                method: "get_characters",
                params: ["path": path],
                id: "characters-\(UUID().uuidString)"
            )
        } catch {
            activity.append(ActivityEntry(kind: .error, message: error.localizedDescription))
        }
    }

    func selectCharacter(_ id: String?) {
        selectedCharacterID = id
        guard let id, let character = characters.first(where: { $0.id == id }) else {
            characterDraft = CharacterDraft()
            return
        }
        characterDraft = CharacterDraft(character: character)
        characterSaveMessage = ""
    }

    func saveSelectedCharacter() {
        guard let path = selectedCharacterMapPath,
              let characterID = selectedCharacterID else { return }
        do {
            characterSaveMessage = "Saving…"
            _ = try backend.send(
                method: "update_character",
                params: [
                    "path": path,
                    "character_id": characterID,
                    "updates": characterDraft.updates,
                ],
                id: "save-character-\(UUID().uuidString)"
            )
        } catch {
            characterSaveMessage = error.localizedDescription
        }
    }

    func previewSelectedVoice() {
        guard selectedCharacterID != nil else { return }
        let text = characterDraft.displayName.isEmpty
            ? "This is the selected character speaking in English."
            : "This is \(characterDraft.displayName) speaking in English."

        let inheritedProvider = characterDraft.ttsProvider == "inherit"
            ? voiceProvider.rawValue
            : characterDraft.ttsProvider
        let reference = characterDraft.referenceAudio.isEmpty
            ? chatterboxReferenceAudio
            : characterDraft.referenceAudio
        let selectedKokoro = characterDraft.kokoroVoice.isEmpty
            ? kokoroVoice
            : characterDraft.kokoroVoice

        do {
            _ = try backend.send(
                method: "preview_voice",
                params: [
                    "provider": inheritedProvider,
                    "voice": characterDraft.macosVoice,
                    "text": text,
                    "rate": characterDraft.ttsRate,
                    "reference_audio": reference,
                    "expressiveness": characterDraft.expressiveness,
                    "device": chatterboxDevice,
                    "turbo": chatterboxTurbo,
                    "kokoro_voice": selectedKokoro,
                    "voice_class": characterDraft.voiceClass,
                    "age_group": characterDraft.ageGroup,
                    "piper_model": piperModel,
                    "piper_speaker": piperSpeaker,
                    "api_key": elevenLabsAPIKey,
                    "voice_id": characterDraft.elevenLabsVoiceID.isEmpty ? elevenLabsVoiceID : characterDraft.elevenLabsVoiceID,
                ],
                id: "preview-\(UUID().uuidString)"
            )
        } catch {
            activity.append(ActivityEntry(kind: .error, message: error.localizedDescription))
        }
    }

    func chooseSourceFile() {
        let panel = NSOpenPanel()
        panel.title = "Choose Source Video"
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.allowedContentTypes = [.movie, .video]
        if panel.runModal() == .OK, let url = panel.url {
            source = url.path
        }
    }

    func chooseOutputFolder() {
        let panel = NSOpenPanel()
        panel.title = "Choose Output Folder"
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        if panel.runModal() == .OK, let url = panel.url {
            outputFolder = url.path
            savePreferences()
        }
    }

    func choosePiperModel() {
        let panel = NSOpenPanel()
        panel.title = "Choose Piper Voice Model"
        panel.canChooseDirectories = false
        panel.canChooseFiles = true
        panel.allowsMultipleSelection = false
        if let onnx = UTType(filenameExtension: "onnx") {
            panel.allowedContentTypes = [onnx]
        }
        if panel.runModal() == .OK, let url = panel.url {
            piperModel = url.path
            savePreferences()
        }
    }

    func chooseChatterboxReference() {
        let panel = NSOpenPanel()
        panel.title = "Choose Voice Reference Clip"
        panel.canChooseDirectories = false
        panel.canChooseFiles = true
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = [.audio]
        if panel.runModal() == .OK, let url = panel.url {
            chatterboxReferenceAudio = url.path
            savePreferences()
        }
    }

    func chooseCharacterReference() {
        let panel = NSOpenPanel()
        panel.title = "Choose Character Voice Reference Clip"
        panel.canChooseDirectories = false
        panel.canChooseFiles = true
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = [.audio]
        if panel.runModal() == .OK, let url = panel.url {
            characterDraft.referenceAudio = url.path
        }
    }

    private func handleBackendMessage(_ payload: [String: Any]) {
        let type = payload["type"] as? String ?? ""

        if type == "response" {
            handleResponse(payload)
        } else if type == "event" {
            handleEvent(payload)
        }
    }

    private func handleResponse(_ payload: [String: Any]) {
        let id = payload["id"] as? String ?? ""
        let ok = payload["ok"] as? Bool ?? false

        if !ok {
            let error = payload["error"] as? [String: Any]
            let message = error?["message"] as? String ?? "Backend request failed."
            activity.append(ActivityEntry(kind: .error, message: message))
            statusText = message
            if id.hasPrefix("save-character-") {
                characterSaveMessage = message
            }
            return
        }

        let resultAny = payload["result"]
        let result = resultAny as? [String: Any] ?? [:]

        switch id {
        case "hello":
            let version = result["version"] as? String ?? "ready"
            backendState = .ready(version: version)
            statusText = "Ready"
            _ = try? backend.send(method: "list_voices", id: "voices")
            refreshProjects()
            refreshCharacterMaps()

        case "voices":
            installedVoices = resultAny as? [String] ?? []

        case "system-check":
            let checks = result["checks"] as? [[String: Any]] ?? []
            systemCheckItems = checks.map {
                SystemCheckItem(
                    name: $0["name"] as? String ?? "Unknown",
                    ok: $0["ok"] as? Bool ?? false,
                    detail: $0["detail"] as? String ?? ""
                )
            }
            showingSystemCheck = true

        default:
            if id.hasPrefix("run-") || id.hasPrefix("analyze-") {
                if let jobID = result["job_id"] as? String {
                    activeJobID = jobID
                    statusText = "Queued"
                    activity.append(ActivityEntry(kind: .info, message: "Started \(jobID)."))
                    refreshProjects()
                }
            } else if id.hasPrefix("projects-") {
                let rows = resultAny as? [[String: Any]] ?? []
                projects = rows.compactMap(ProjectSummary.init(dictionary:))
                if selectedProjectID == nil {
                    selectedProjectID = projects.first?.id
                }
            } else if id.hasPrefix("character-maps-") {
                let rows = resultAny as? [[String: Any]] ?? []
                characterMaps = rows.compactMap(CharacterMapSummary.init(dictionary:))
                if let selected = selectedCharacterMapPath,
                   characterMaps.contains(where: { $0.path == selected }) {
                    loadCharacterMap(selected)
                } else if let first = characterMaps.first {
                    loadCharacterMap(first.path)
                } else {
                    selectedCharacterMapPath = nil
                    characters = []
                    selectedCharacterID = nil
                }
            } else if id.hasPrefix("characters-") {
                let rows = result["characters"] as? [[String: Any]] ?? []
                characters = rows.compactMap(CharacterItem.init(dictionary:))
                    .sorted { $0.speakingShare > $1.speakingShare }
                if let first = characters.first {
                    selectCharacter(first.id)
                } else {
                    selectCharacter(nil)
                }
            } else if id.hasPrefix("save-character-") {
                if let saved = CharacterItem(dictionary: result),
                   let index = characters.firstIndex(where: { $0.id == saved.id }) {
                    characters[index] = saved
                    selectCharacter(saved.id)
                }
                characterSaveMessage = "Saved"
                activity.append(ActivityEntry(kind: .info, message: "Saved character voice override."))
            }
        }
    }

    private func handleEvent(_ payload: [String: Any]) {
        let event = payload["event"] as? String ?? ""
        let data = payload["data"] as? [String: Any] ?? [:]

        switch event {
        case "stage":
            let title = data["title"] as? String ?? "Working"
            statusText = title
            if let fraction = data["fraction"] as? Double {
                progressFraction = fraction
            }

        case "progress":
            statusText = data["title"] as? String ?? "Working"
            progressFraction = data["fraction"] as? Double

        case "log":
            if let message = data["message"] as? String, !message.isEmpty {
                activity.append(ActivityEntry(kind: .info, message: message))
            }

        case "warning":
            activity.append(ActivityEntry(kind: .warning, message: data["message"] as? String ?? "Warning"))

        case "artifact":
            let kind = data["kind"] as? String ?? "output"
            let path = data["path"] as? String ?? ""
            activity.append(ActivityEntry(kind: .artifact, message: "\(kind): \(path)"))

        case "error":
            activity.append(ActivityEntry(kind: .error, message: data["message"] as? String ?? "Backend error"))
            statusText = "Failed"

        case "finished":
            let status = data["status"] as? String ?? "completed"
            activeJobID = nil
            progressFraction = status == "completed" ? 1 : nil
            statusText = status == "completed" ? "Completed" : status.capitalized
            refreshProjects()
            refreshCharacterMaps()

        default:
            break
        }
    }
}
