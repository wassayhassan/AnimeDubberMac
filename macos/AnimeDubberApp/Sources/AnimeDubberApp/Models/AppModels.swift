import SwiftUI

enum SidebarDestination: String, CaseIterable, Identifiable, Hashable {
    case newDub
    case projects
    case characters
    case activity
    case settings

    var id: String { rawValue }

    var title: String {
        switch self {
        case .newDub: "New Dub"
        case .projects: "Projects"
        case .characters: "Characters"
        case .activity: "Activity"
        case .settings: "Settings"
        }
    }

    var symbol: String {
        switch self {
        case .newDub: "waveform.badge.plus"
        case .projects: "square.stack.3d.up"
        case .characters: "person.2"
        case .activity: "list.bullet.rectangle"
        case .settings: "gearshape"
        }
    }
}

enum OutputMode: String, CaseIterable, Identifiable {
    case dub
    case subtitles

    var id: String { rawValue }
    var title: String {
        switch self {
        case .dub: "English dub + subtitles"
        case .subtitles: "Subtitles only"
        }
    }
}

enum ASRProvider: String, CaseIterable, Identifiable {
    case auto
    case mlxWhisper = "mlx_whisper"
    case fasterWhisper = "faster_whisper"

    var id: String { rawValue }

    var title: String {
        switch self {
        case .auto: "Automatic"
        case .mlxWhisper: "MLX Whisper"
        case .fasterWhisper: "Faster-Whisper"
        }
    }
}

enum TranslationProvider: String, CaseIterable, Identifiable {
    case auto
    case llm
    case ollama
    case whisper

    var id: String { rawValue }
    var title: String {
        switch self {
        case .auto: "Automatic"
        case .llm: "Local MLX LLM"
        case .ollama: "Ollama"
        case .whisper: "Whisper direct"
        }
    }
}

enum VoiceProvider: String, CaseIterable, Identifiable {
    case auto
    case chatterbox
    case kokoro
    case elevenlabs
    case macos
    case piper

    var id: String { rawValue }
    var title: String {
        switch self {
        case .auto: "Automatic · Best Local"
        case .chatterbox: "Chatterbox Turbo"
        case .kokoro: "Kokoro · Fast Local"
        case .elevenlabs: "ElevenLabs"
        case .macos: "macOS Voice"
        case .piper: "Piper"
        }
    }
}

enum BackendConnectionState: Equatable {
    case disconnected
    case connecting
    case ready(version: String)
    case failed(String)

    var label: String {
        switch self {
        case .disconnected: "Backend Offline"
        case .connecting: "Connecting…"
        case .ready(let version): "Backend \(version)"
        case .failed: "Backend Error"
        }
    }

    var color: Color {
        switch self {
        case .ready: .green
        case .connecting: .orange
        case .disconnected, .failed: .red
        }
    }
}

struct ActivityEntry: Identifiable {
    enum Kind {
        case info
        case warning
        case error
        case artifact
    }

    let id = UUID()
    let date = Date()
    let kind: Kind
    let message: String

    var symbol: String {
        switch kind {
        case .info: "circle.fill"
        case .warning: "exclamationmark.triangle.fill"
        case .error: "xmark.octagon.fill"
        case .artifact: "doc.fill"
        }
    }

    var tint: Color {
        switch kind {
        case .info: .secondary
        case .warning: .orange
        case .error: .red
        case .artifact: .blue
        }
    }
}

struct SystemCheckItem: Identifiable {
    let id = UUID()
    let name: String
    let ok: Bool
    let detail: String
}


struct ProjectSummary: Identifiable {
    let id: String
    let source: String
    let seriesID: String
    let outputDir: String
    let status: String
    let stage: String
    let stageTitle: String
    let progress: Double?
    let updatedAt: String
    let artifacts: [String: String]
    let warningCount: Int
    let lastError: String?

    init?(dictionary: [String: Any]) {
        guard let projectID = dictionary["project_id"] as? String, !projectID.isEmpty else { return nil }
        id = projectID
        source = dictionary["source"] as? String ?? ""
        seriesID = dictionary["series_id"] as? String ?? ""
        outputDir = dictionary["output_dir"] as? String ?? ""
        status = dictionary["status"] as? String ?? "unknown"
        stage = dictionary["stage"] as? String ?? ""
        stageTitle = dictionary["stage_title"] as? String ?? ""
        if let number = dictionary["progress"] as? NSNumber {
            progress = number.doubleValue
        } else {
            progress = nil
        }
        updatedAt = dictionary["updated_at"] as? String ?? ""
        artifacts = dictionary["artifacts"] as? [String: String] ?? [:]
        warningCount = (dictionary["warning_count"] as? NSNumber)?.intValue ?? 0
        lastError = dictionary["last_error"] as? String
    }

    var displayName: String {
        if !seriesID.isEmpty { return seriesID }
        if source.hasPrefix("http") { return id }
        let url = URL(fileURLWithPath: source)
        return url.lastPathComponent.isEmpty ? id : url.lastPathComponent
    }

    var statusLabel: String {
        status.replacingOccurrences(of: "_", with: " ").capitalized
    }
}

struct CharacterMapSummary: Identifiable, Hashable {
    let path: String
    let sourceKey: String
    let seriesID: String
    let speakerBackend: String
    let characterCount: Int
    let modifiedAt: Double

    var id: String { path }

    init?(dictionary: [String: Any]) {
        guard let path = dictionary["path"] as? String, !path.isEmpty else { return nil }
        self.path = path
        sourceKey = dictionary["source_key"] as? String ?? ""
        seriesID = dictionary["series_id"] as? String ?? ""
        speakerBackend = dictionary["speaker_backend"] as? String ?? ""
        characterCount = (dictionary["character_count"] as? NSNumber)?.intValue ?? 0
        modifiedAt = (dictionary["modified_at"] as? NSNumber)?.doubleValue ?? 0
    }

    var displayName: String {
        seriesID.isEmpty ? sourceKey : seriesID
    }
}

struct CharacterItem: Identifiable, Hashable {
    let id: String
    var displayName: String
    var role: String
    var voiceClass: String
    var ageGroup: String
    let lineCount: Int
    let speakingShare: Double
    var ttsProvider: String
    var macosVoice: String
    var kokoroVoice: String
    var referenceAudio: String
    var expressiveness: Double
    var elevenLabsVoiceID: String
    var ttsRate: Int
    var pitchSemitones: Double
    var voiceGain: Double
    var notes: String
    var manual: Bool

    init?(dictionary: [String: Any]) {
        guard let id = dictionary["id"] as? String, !id.isEmpty else { return nil }
        self.id = id
        displayName = dictionary["display_name"] as? String ?? id
        role = dictionary["role"] as? String ?? "minor"
        voiceClass = dictionary["voice_class"] as? String ?? "neutral"
        ageGroup = dictionary["age_group"] as? String ?? "adult"
        lineCount = (dictionary["line_count"] as? NSNumber)?.intValue ?? 0
        speakingShare = (dictionary["speaking_share"] as? NSNumber)?.doubleValue ?? 0
        ttsProvider = dictionary["tts_provider"] as? String ?? "inherit"
        macosVoice = dictionary["macos_voice"] as? String ?? ""
        kokoroVoice = dictionary["kokoro_voice"] as? String ?? "auto"
        referenceAudio = dictionary["reference_audio"] as? String ?? ""
        expressiveness = (dictionary["expressiveness"] as? NSNumber)?.doubleValue ?? 0.5
        elevenLabsVoiceID = dictionary["elevenlabs_voice_id"] as? String ?? ""
        ttsRate = (dictionary["tts_rate"] as? NSNumber)?.intValue ?? 205
        pitchSemitones = (dictionary["pitch_semitones"] as? NSNumber)?.doubleValue ?? 0
        voiceGain = (dictionary["voice_gain"] as? NSNumber)?.doubleValue ?? 1
        notes = dictionary["notes"] as? String ?? ""
        manual = dictionary["manual"] as? Bool ?? false
    }
}

struct CharacterDraft: Equatable {
    var displayName = ""
    var role = "minor"
    var voiceClass = "neutral"
    var ageGroup = "adult"
    var ttsProvider = "inherit"
    var macosVoice = ""
    var kokoroVoice = "auto"
    var referenceAudio = ""
    var expressiveness = 0.5
    var elevenLabsVoiceID = ""
    var ttsRate = 205
    var pitchSemitones = 0.0
    var voiceGain = 1.0
    var notes = ""

    init() {}

    init(character: CharacterItem) {
        displayName = character.displayName
        role = character.role
        voiceClass = character.voiceClass
        ageGroup = character.ageGroup
        ttsProvider = character.ttsProvider
        macosVoice = character.macosVoice
        kokoroVoice = character.kokoroVoice
        referenceAudio = character.referenceAudio
        expressiveness = character.expressiveness
        elevenLabsVoiceID = character.elevenLabsVoiceID
        ttsRate = character.ttsRate
        pitchSemitones = character.pitchSemitones
        voiceGain = character.voiceGain
        notes = character.notes
    }

    var updates: [String: Any] {
        [
            "display_name": displayName,
            "role": role,
            "voice_class": voiceClass,
            "age_group": ageGroup,
            "tts_provider": ttsProvider,
            "macos_voice": macosVoice,
            "kokoro_voice": kokoroVoice,
            "reference_audio": referenceAudio,
            "expressiveness": expressiveness,
            "elevenlabs_voice_id": elevenLabsVoiceID,
            "tts_rate": ttsRate,
            "pitch_semitones": pitchSemitones,
            "voice_gain": voiceGain,
            "notes": notes,
        ]
    }
}
