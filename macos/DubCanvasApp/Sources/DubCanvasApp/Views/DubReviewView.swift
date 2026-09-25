import AppKit
import AVKit
import SwiftUI

private struct DubReviewNote: Identifiable {
    let id: Int
    let start: Double
    let source: String
    let translation: String
    let suggestion: String
    let reasons: [String]
}

struct DubReviewView: View {
    @EnvironmentObject private var state: AppState
    let dubID: String
    @State private var notes: [DubReviewNote] = []
    @State private var selectedID: Int?
    @State private var filter = ""
    @State private var player: AVPlayer?
    @State private var issue: String?

    private var dub: DubSummary? { state.currentProject?.dubs.first { $0.id == dubID } }
    private var selected: DubReviewNote? { notes.first { $0.id == selectedID } }
    private var visible: [DubReviewNote] {
        filter.isEmpty ? notes : notes.filter {
            $0.source.localizedCaseInsensitiveContains(filter) ||
            $0.translation.localizedCaseInsensitiveContains(filter) ||
            $0.reasons.joined(separator: " ").localizedCaseInsensitiveContains(filter)
        }
    }

    var body: some View {
        Group {
            if let dub {
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        VStack(alignment: .leading) {
                            Text("Review Notes").font(.largeTitle.bold())
                            Text("\(state.currentProject?.displayName ?? "Project") / \(dub.title)")
                                .foregroundStyle(.secondary)
                        }
                        Spacer()
                        Button("Back to Result") { state.selection = .dub(dub.id) }
                    }
                    Text("Automatic review helps identify uncertain lines and timing. Check the video before sharing; these notes do not imply that other lines were verified.")
                        .font(.callout).foregroundStyle(.secondary)
                    if let issue { Label(issue, systemImage: "exclamationmark.triangle").foregroundStyle(.orange) }
                    HStack(alignment: .top, spacing: 16) {
                        VStack(alignment: .leading) {
                            TextField("Search text or reason", text: $filter)
                                .textFieldStyle(.roundedBorder)
                            Text("\(visible.count) notes").font(.caption).foregroundStyle(.secondary)
                            List(visible, selection: $selectedID) { note in
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(String(format: "%02d:%02d · Cue %d", Int(note.start) / 60, Int(note.start) % 60, note.id))
                                        .font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                                    Text(note.translation).lineLimit(2)
                                    Text(note.reasons.joined(separator: ", ").replacingOccurrences(of: "_", with: " "))
                                        .font(.caption).foregroundStyle(.orange)
                                }.padding(.vertical, 4).tag(note.id)
                            }.listStyle(.inset)
                        }
                        .frame(minWidth: 270, idealWidth: 350)
                        VStack(alignment: .leading, spacing: 12) {
                            if let player {
                                NativeDubPlayer(player: player)
                                    .frame(minHeight: 220, maxHeight: 310)
                                    .clipShape(RoundedRectangle(cornerRadius: 10))
                            }
                            if let selected {
                                GroupBox("Cue \(selected.id)") {
                                    VStack(alignment: .leading, spacing: 10) {
                                        LabeledContent("Source", value: selected.source)
                                        LabeledContent("Translation", value: selected.translation)
                                        if !selected.suggestion.isEmpty {
                                            LabeledContent("Model suggestion", value: selected.suggestion)
                                        }
                                        Label(selected.reasons.joined(separator: ", ").replacingOccurrences(of: "_", with: " "), systemImage: "exclamationmark.triangle")
                                            .foregroundStyle(.orange)
                                        Button("Play This Moment") { seek(to: selected.start) }
                                    }.frame(maxWidth: .infinity, alignment: .leading)
                                }
                            } else {
                                ContentUnavailableView("Choose a Note", systemImage: "text.magnifyingglass",
                                    description: Text("Select a cue to inspect source and translated text beside the video."))
                            }
                            Spacer(minLength: 0)
                        }.frame(maxWidth: .infinity, alignment: .topLeading)
                    }
                }
                .padding(24)
                .onAppear { load(dub) }
                .onChange(of: dubID) { _, _ in if let updated = self.dub { load(updated) } }
                .onChange(of: selectedID) { _, _ in
                    if let selected { seek(to: selected.start, play: false) }
                }
                .onDisappear { player?.pause() }
            } else {
                ContentUnavailableView("Dub Not Found", systemImage: "waveform", description: Text("Open a dub version first."))
            }
        }
        .navigationTitle("Review Notes")
    }

    private func seek(to seconds: Double, play: Bool = true) {
        player?.seek(to: CMTime(seconds: max(0, seconds - 0.25), preferredTimescale: 600)) { _ in
            if play { player?.play() }
        }
    }

    private func load(_ dub: DubSummary) {
        notes = []
        issue = nil
        let videoPath = dub.artifacts["dubbed_video"] ?? dub.artifacts["source_video"] ?? ""
        player = FileManager.default.fileExists(atPath: videoPath) ? AVPlayer(url: URL(fileURLWithPath: videoPath)) : nil
        guard let path = dub.artifacts["review_report"],
              let data = try? Data(contentsOf: URL(fileURLWithPath: path)),
              let report = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              let flags = report["flags"] as? [[String: Any]] else {
            issue = "The review report is unavailable at its saved location."
            return
        }
        notes = flags.compactMap { row in
            guard let id = row["cue"] as? Int else { return nil }
            return DubReviewNote(id: id, start: (row["start"] as? NSNumber)?.doubleValue ?? 0,
                                 source: row["source"] as? String ?? "",
                                 translation: row["translation"] as? String ?? "",
                                 suggestion: row["suggestion"] as? String ?? "",
                                 reasons: row["reasons"] as? [String] ?? [])
        }
        selectedID = notes.first?.id
    }
}
