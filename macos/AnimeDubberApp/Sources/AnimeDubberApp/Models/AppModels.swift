import SwiftUI

enum SidebarDestination: String, CaseIterable, Identifiable {
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

enum TranslationProvider: String, CaseIterable, Identifiable {
    case llm
    case whisper

    var id: String { rawValue }
    var title: String {
        switch self {
        case .llm: "Local LLM"
        case .whisper: "Whisper direct"
        }
    }
}

enum VoiceProvider: String, CaseIterable, Identifiable {
    case macos
    case elevenlabs

    var id: String { rawValue }
    var title: String {
        switch self {
        case .macos: "macOS Local"
        case .elevenlabs: "ElevenLabs"
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
