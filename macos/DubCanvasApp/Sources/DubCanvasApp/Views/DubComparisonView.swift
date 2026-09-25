import AVKit
import SwiftUI

struct DubComparisonView: View {
    let project: ProjectSummary
    @Environment(\.dismiss) private var dismiss
    @State private var firstID = ""
    @State private var secondID = ""
    @State private var firstPlayer: AVPlayer?
    @State private var secondPlayer: AVPlayer?
    @State private var time = 0.0

    private var versions: [DubSummary] {
        project.dubs.filter { $0.status == "completed" && $0.artifacts["dubbed_video"] != nil }
    }
    private var first: DubSummary? { versions.first { $0.id == firstID } }
    private var second: DubSummary? { versions.first { $0.id == secondID } }
    private var maximumTime: Double { max(1, min(first?.duration ?? 1, second?.duration ?? 1)) }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                VStack(alignment: .leading) {
                    Text("Compare Dub Versions").font(.title2.bold())
                    Text(project.displayName).foregroundStyle(.secondary)
                }
                Spacer()
                Button("Done") { dismiss() }
            }
            HStack {
                Picker("Version A", selection: $firstID) {
                    ForEach(versions) { dub in Text(dub.title).tag(dub.id) }
                }
                Picker("Version B", selection: $secondID) {
                    ForEach(versions) { dub in Text(dub.title).tag(dub.id) }
                }
            }
            if firstID == secondID {
                Label("Choose two different versions.", systemImage: "info.circle")
                    .foregroundStyle(.secondary)
            }
            HStack(alignment: .top, spacing: 14) {
                comparisonColumn(first, player: firstPlayer, label: "A")
                comparisonColumn(second, player: secondPlayer, label: "B")
            }
            if let first, let second, first.analysisRevision != second.analysisRevision {
                Label("These versions used different source analysis revisions. Matching timestamps may contain different cues.", systemImage: "exclamationmark.triangle")
                    .foregroundStyle(.orange)
            }
            if firstID != secondID, firstPlayer != nil, secondPlayer != nil,
               first?.duration != nil, second?.duration != nil {
                HStack {
                    Text("0:00").monospacedDigit()
                    Slider(value: $time, in: 0...maximumTime) { Text("Source time") }
                        .onChange(of: time) { _, newTime in seekBoth(to: newTime) }
                    Text(String(format: "%d:%02d", Int(maximumTime) / 60, Int(maximumTime) % 60))
                        .monospacedDigit()
                }
                Text("Both previews seek to the same source timestamp. Play one at a time to compare voices and timing.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Spacer(minLength: 0)
        }
        .padding(22)
        .onAppear {
            firstID = versions.first?.id ?? ""
            secondID = versions.dropFirst().first?.id ?? ""
            loadPlayers()
        }
        .onChange(of: firstID) { _, _ in loadPlayers() }
        .onChange(of: secondID) { _, _ in loadPlayers() }
        .onDisappear { firstPlayer?.pause(); secondPlayer?.pause() }
    }

    @ViewBuilder private func comparisonColumn(_ dub: DubSummary?, player: AVPlayer?, label: String) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("\(label) · \(dub?.title ?? "Select a version")").font(.headline)
            if let player {
                NativeDubPlayer(player: player)
                    .frame(height: 230)
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                Button("Play \(label)") {
                    if label == "A" { secondPlayer?.pause() } else { firstPlayer?.pause() }
                    player.play()
                }
            } else {
                ContentUnavailableView("Video Missing", systemImage: "film",
                    description: Text("This version's rendered video is unavailable."))
                    .frame(height: 230)
            }
            if let dub {
                LabeledContent("Language", value: dub.language.uppercased())
                LabeledContent("Voices", value: dub.config["tts_engine"] as? String ?? "Automatic")
                LabeledContent("Translation", value: dub.config["translation"] as? String ?? "Automatic")
                LabeledContent("Review notes", value: "\(dub.warnings.count)")
                LabeledContent("Source analysis", value: dub.analysisRevision == 0 ? "Legacy / unknown" : "Revision \(dub.analysisRevision)")
                if let srt = dub.artifacts["translated_srt"] ?? dub.artifacts["english_srt"] {
                    Button("Save subtitles…") { exportFile(srt) }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private func loadPlayers() {
        firstPlayer?.pause()
        secondPlayer?.pause()
        firstPlayer = player(for: first)
        secondPlayer = player(for: second)
        seekBoth(to: time)
    }

    private func player(for dub: DubSummary?) -> AVPlayer? {
        guard let path = dub?.artifacts["dubbed_video"],
              FileManager.default.fileExists(atPath: path) else { return nil }
        return AVPlayer(url: URL(fileURLWithPath: path))
    }

    private func seekBoth(to seconds: Double) {
        firstPlayer?.pause()
        secondPlayer?.pause()
        let position = CMTime(seconds: seconds, preferredTimescale: 600)
        firstPlayer?.seek(to: position)
        secondPlayer?.seek(to: position)
    }
}
