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
    @Published var translationProvider: TranslationProvider = .llm
    @Published var voiceProvider: VoiceProvider = .macos
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

    private let backend = BackendProcess()

    init() {
        connectBackend()
    }

    deinit {
        backend.stop()
    }

    var canStartJob: Bool {
        guard case .ready = backendState else { return false }
        return !source.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && activeJobID == nil
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

        let threshold: Any = speakerThreshold == 0 ? NSNull() : speakerThreshold

        let params: [String: Any] = [
            "source": source,
            "output_dir": outputFolder,
            "series_id": seriesID,
            "mode": outputMode.rawValue,
            "translation": ["provider": translationProvider.rawValue],
            "tts": ["provider": voiceProvider.rawValue],
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
            return
        }

        let result = payload["result"] as? [String: Any] ?? [:]

        switch id {
        case "hello":
            let version = result["version"] as? String ?? "ready"
            backendState = .ready(version: version)
            statusText = "Ready"

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
                }
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

        default:
            break
        }
    }
}
