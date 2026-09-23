import AVKit
import SwiftUI

struct DubDetailsView: View {
    @EnvironmentObject private var state: AppState
    let dubID: String
    @State private var player: AVPlayer?
    @State private var confirmDelete = false
    @State private var advancedExpanded = false
    @State private var voiceAssignments: [String] = []
    @State private var reviewCues: [ReviewCue] = []
    @State private var reviewDraft: [Int: String] = [:]
    @State private var reviewMessage = ""

    private struct ReviewCue: Identifiable {
        let id: Int
        let source: String
        let translation: String
        let suggestion: String
        let alternate: String
        let reasons: [String]
        let duration: Double?
        let available: Double?
        let error: String
    }

    private var dub: DubSummary? { state.currentProject?.dubs.first { $0.id == dubID } }

    var body: some View {
        ScrollView {
            if let dub {
                VStack(alignment: .leading, spacing: 18) {
                    VStack(alignment: .leading, spacing: 8) {
                        Label(dub.title, systemImage: "waveform.circle.fill")
                            .font(.largeTitle.bold())
                        HStack {
                            Label(dub.status.capitalized, systemImage: dub.status == "completed" ? "checkmark.circle.fill" : "clock")
                            Text("· \(dub.language.uppercased())")
                            Text("· Created \(dub.createdAt)")
                        }.font(.callout).foregroundStyle(.secondary)
                    }

                    if let player {
                        NativeDubPlayer(player: player)
                            .frame(height: 340)
                            .clipShape(RoundedRectangle(cornerRadius: 10))
                    } else if dub.status == "completed" {
                        Text("The rendered video is unavailable at its recorded path.")
                            .foregroundStyle(.secondary)
                    }

                    GroupBox("Overview") {
                        detailGrid([
                            ("Target language", dub.language.uppercased()),
                            ("Source language", dub.sourceLanguage.uppercased()),
                            ("Translation model", value(dub.config, "translation") + modelSuffix(dub.config)),
                            ("Speech engine", value(dub.config, "tts_engine")),
                            ("Voice", value(dub.config, "voice")),
                            ("Duration", dub.duration.map { String(format: "%.1f s", $0) } ?? "Pending"),
                            ("Processing stage", dub.stage.capitalized),
                            ("Updated", dub.updatedAt),
                        ])
                    }
                    GroupBox("Timing and voices") {
                        VStack(alignment: .leading, spacing: 10) {
                            Label(dub.sync, systemImage: "waveform.path")
                            Text("Timing follows the source speech windows. Review the rendered video for any line that needs manual adjustment.")
                                .font(.caption).foregroundStyle(.secondary)
                            if let path = dub.artifacts["character_map"] {
                                ArtifactLink(title: "Character voice assignments", path: path)
                                ForEach(voiceAssignments, id: \.self) { assignment in
                                    Label(assignment, systemImage: "person.wave.2")
                                        .font(.caption)
                                }
                                Button("Edit Current Character Voices") {
                                    state.loadCharacterMap(path)
                                    state.selection = .characters
                                }
                            }
                        }.frame(maxWidth: .infinity, alignment: .leading)
                    }
                    if dub.status == "paused" && dub.error == "Subtitle review required before voice generation" {
                        GroupBox("Review Subtitles Before Dubbing") {
                            VStack(alignment: .leading, spacing: 14) {
                                Text("Compare the source and translation. Use a shorter suggestion if one is available, or edit the wording yourself. The app checks the generated voice duration again when you continue.")
                                    .foregroundStyle(.secondary)
                                if !reviewMessage.isEmpty { Text(reviewMessage).foregroundStyle(.orange) }
                                ForEach(reviewCues) { cue in
                                    VStack(alignment: .leading, spacing: 6) {
                                        Text("Cue \(cue.id) · \(cue.reasons.joined(separator: ", ").replacingOccurrences(of: "_", with: " "))")
                                            .font(.caption).foregroundStyle(.secondary)
                                        if let duration = cue.duration, let available = cue.available {
                                            Text(String(format: "Voice takes %.2f seconds; %.2f seconds available before the next line.", duration, available))
                                                .font(.caption).foregroundStyle(.orange)
                                        }
                                        Text(cue.source).textSelection(.enabled)
                                        Text("Current: \(cue.translation)").font(.callout)
                                        if !cue.error.isEmpty { Text(cue.error).font(.caption).foregroundStyle(.orange) }
                                        if !cue.alternate.isEmpty {
                                            Text("Alternate transcription (unverified): \(cue.alternate)")
                                                .font(.caption).foregroundStyle(.orange)
                                        }
                                        TextField("Approved translation", text: Binding(
                                            get: { reviewDraft[cue.id] ?? cue.translation },
                                            set: { reviewDraft[cue.id] = $0 }
                                        ))
                                        .textFieldStyle(.roundedBorder)
                                        HStack {
                                            if !cue.suggestion.isEmpty {
                                                Text("Suggestion: \(cue.suggestion)").textSelection(.enabled)
                                                Button("Use suggestion") {
                                                    reviewDraft[cue.id] = cue.suggestion
                                                }.buttonStyle(.link)
                                            }
                                            Spacer()
                                            if !cue.reasons.contains("speech_overlap") {
                                                Button("Use original") { reviewDraft[cue.id] = cue.translation }
                                                    .buttonStyle(.link)
                                            }
                                        }.font(.caption)
                                    }
                                    Divider()
                                }
                                Button("Approve and Continue Dub", systemImage: "checkmark.circle") {
                                    let revisions = Dictionary(uniqueKeysWithValues: reviewCues.compactMap { cue -> (String, String)? in
                                        let value = (reviewDraft[cue.id] ?? cue.translation).trimmingCharacters(in: .whitespacesAndNewlines)
                                        return value != cue.translation && !value.isEmpty ? (String(cue.id), value) : nil
                                    })
                                    if reviewCues.contains(where: { (reviewDraft[$0.id] ?? $0.translation).trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }) {
                                        reviewMessage = "An approved line cannot be empty."
                                    } else if reviewCues.contains(where: { $0.reasons.contains("speech_overlap") &&
                                        (reviewDraft[$0.id] ?? $0.translation).trimmingCharacters(in: .whitespacesAndNewlines) == $0.translation }) {
                                        reviewMessage = "A line overlaps the next voice. Give it shorter wording before continuing."
                                    } else {
                                        state.approveReview(dub, revisions: revisions)
                                    }
                                }
                                .buttonStyle(.borderedProminent)
                                .disabled(state.activeJobID != nil || reviewCues.isEmpty)
                            }.frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                    GroupBox("Files") {
                        VStack(alignment: .leading, spacing: 12) {
                            if dub.artifacts.isEmpty {
                                Text("Files appear here as each processing stage finishes.")
                                    .foregroundStyle(.secondary)
                            }
                            ForEach(dub.artifacts.keys.sorted(), id: \.self) { kind in
                                if let path = dub.artifacts[kind] {
                                    ArtifactLink(title: kind.replacingOccurrences(of: "_", with: " ").capitalized, path: path)
                                }
                            }
                        }.frame(maxWidth: .infinity, alignment: .leading)
                    }
                    GroupBox {
                        DisclosureGroup("Full generation settings", isExpanded: $advancedExpanded) {
                            VStack(alignment: .leading, spacing: 8) {
                                ForEach(dub.config.keys.sorted(), id: \.self) { key in
                                    if !["source", "output_dir", "elevenlabs_api_key"].contains(key) {
                                        LabeledContent(key.replacingOccurrences(of: "_", with: " ").capitalized,
                                                       value: String(describing: dub.config[key] ?? "—"))
                                            .font(.caption)
                                    }
                                }
                            }.padding(.top, 10).frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                    if !dub.warnings.isEmpty || dub.error != nil {
                        GroupBox("Warnings and errors") {
                            VStack(alignment: .leading, spacing: 8) {
                                ForEach(dub.warnings, id: \.self) { message in
                                    Label(message, systemImage: "exclamationmark.triangle").foregroundStyle(.orange)
                                }
                                if let error = dub.error {
                                    Label(error, systemImage: "xmark.octagon").foregroundStyle(.red)
                                }
                            }.frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                    HStack {
                        if (["paused", "failed", "cancelled"].contains(dub.status) &&
                            dub.error != "Subtitle review required before voice generation") ||
                            (dub.status == "running" && state.activeJobID == nil) {
                            Button("Resume This Dub", systemImage: "play.fill") {
                                state.resumeDub(dub)
                            }
                            .disabled(state.activeJobID != nil)
                        }
                        Button("Regenerate as New Version", systemImage: "arrow.clockwise") {
                            state.regenerate(dub)
                        }
                        Spacer()
                        Button("Delete Dub", systemImage: "trash", role: .destructive) {
                            confirmDelete = true
                        }.disabled(dub.status == "running" || dub.id == "legacy")
                    }
                }
                .frame(maxWidth: 900, alignment: .leading)
                .padding(28)
                .frame(maxWidth: .infinity, alignment: .topLeading)
                .confirmationDialog("Delete \(dub.title)?", isPresented: $confirmDelete) {
                    Button("Delete Dub and Its Files", role: .destructive) { state.deleteDub(dub) }
                } message: {
                    Text("This removes this dub's version folder. Shared source media and other dubs stay in the project.")
                }
                .onAppear { loadPlayer(dub); loadReview(dub) }
                .onChange(of: dubID) { _, _ in loadPlayer(dub); loadReview(dub) }
                .onChange(of: dub.artifacts["dubbed_video"]) { _, _ in
                    if let updated = self.dub { loadPlayer(updated) }
                }
                .onChange(of: dub.artifacts["character_map"]) { _, _ in
                    if let updated = self.dub { loadVoiceAssignments(updated) }
                }
                .onChange(of: dub.artifacts["review_report"]) { _, _ in
                    if let updated = self.dub { loadReview(updated) }
                }
                .onChange(of: dub.updatedAt) { _, _ in
                    if let updated = self.dub, updated.status == "paused" { loadReview(updated) }
                }
                .onDisappear { player?.pause() }
            } else {
                ContentUnavailableView("Dub Not Found", systemImage: "waveform", description: Text("Select a dub in the sidebar."))
            }
        }
        .navigationTitle(dub?.title ?? "Dub Details")
    }

    private func loadPlayer(_ dub: DubSummary) {
        loadVoiceAssignments(dub)
        guard let path = dub.artifacts["dubbed_video"], FileManager.default.fileExists(atPath: path) else {
            player = nil
            return
        }
        player = AVPlayer(url: URL(fileURLWithPath: path))
    }

    private func loadVoiceAssignments(_ dub: DubSummary) {
        voiceAssignments = []
        guard let path = dub.artifacts["character_map"],
              let data = try? Data(contentsOf: URL(fileURLWithPath: path)),
              let map = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              let characters = map["characters"] as? [[String: Any]] else { return }
        voiceAssignments = characters.map { item in
            let name = item["display_name"] as? String ?? item["id"] as? String ?? "Character"
            let provider = item["tts_provider"] as? String ?? "inherit"
            let voice = item["elevenlabs_voice_id"] as? String ?? item["kokoro_voice"] as? String ?? item["macos_voice"] as? String ?? ""
            let manual = item["reference_audio"] as? String ?? ""
            let suggested = item["suggested_reference_audio"] as? String ?? ""
            let automatic = item["auto_reference_enabled"] as? Bool ?? true
            let reference = manual.isEmpty && automatic ? suggested : manual
            let source = reference.isEmpty ? "" : " · \(URL(fileURLWithPath: reference).lastPathComponent)"
            return "\(name) · \(provider)\(voice.isEmpty ? "" : " · \(voice)")\(source)"
        }
    }

    private func loadReview(_ dub: DubSummary) {
        reviewCues = []
        reviewDraft = [:]
        reviewMessage = ""
        guard let path = dub.artifacts["review_report"],
              let data = try? Data(contentsOf: URL(fileURLWithPath: path)),
              let report = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              let flags = report["flags"] as? [[String: Any]],
              let priority = report["priority_cues"] as? [Int] else {
            if dub.error == "Subtitle review required before voice generation" {
                reviewMessage = "The review report could not be loaded. Open the report in Files to inspect it."
            }
            return
        }
        let timing = report["timing_issues"] as? [String: [String: Any]] ?? [:]
        let selected = Set(priority).union(timing.keys.compactMap(Int.init))
        reviewMessage = report["review_error"] as? String ?? ""
        reviewCues = flags.compactMap { row in
            guard let cue = row["cue"] as? Int, selected.contains(cue) else { return nil }
            let issue = timing[String(cue)] ?? [:]
            return ReviewCue(id: cue, source: row["source"] as? String ?? "",
                             translation: row["translation"] as? String ?? "",
                             suggestion: row["suggestion"] as? String ?? "",
                             alternate: row["asr_candidate"] as? String ?? "",
                             reasons: row["reasons"] as? [String] ?? [],
                             duration: issue["duration"] as? Double,
                             available: issue["available"] as? Double,
                             error: row["review_error"] as? String ?? "")
        }
        for cue in reviewCues { reviewDraft[cue.id] = cue.translation }
    }

    private func value(_ config: [String: Any], _ key: String) -> String {
        let text = config[key] as? String ?? ""
        return text.isEmpty ? "Automatic / not specified" : text
    }

    private func modelSuffix(_ config: [String: Any]) -> String {
        let key = config["translation"] as? String == "ollama" ? "ollama_model" : "llm_model"
        guard let model = config[key] as? String else { return "" }
        return " · \(model)"
    }

    private func detailGrid(_ items: [(String, String)]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(items, id: \.0) { item in
                LabeledContent(item.0, value: item.1)
            }
        }.frame(maxWidth: .infinity, alignment: .leading)
    }
}

// SwiftUI's VideoPlayer initializes _AVKit_SwiftUI when the details view
// appears. On affected macOS versions that framework aborts while creating
// class metadata. The AppKit player avoids that bridge and keeps playback
// controls inside the project workspace.
private struct NativeDubPlayer: NSViewRepresentable {
    let player: AVPlayer

    func makeNSView(context: Context) -> AVPlayerView {
        let view = AVPlayerView()
        view.controlsStyle = .floating
        view.player = player
        return view
    }

    func updateNSView(_ view: AVPlayerView, context: Context) {
        if view.player !== player {
            view.player = player
        }
    }
}
