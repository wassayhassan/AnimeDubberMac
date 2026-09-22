import AppKit
import AVKit
import SwiftUI

struct ProjectWorkspaceView: View {
    @EnvironmentObject private var state: AppState

    var body: some View {
        ScrollView {
            if let project = state.currentProject {
                VStack(alignment: .leading, spacing: 20) {
                    header(project)
                    switch state.selection ?? .overview {
                    case .media: media(project)
                    case .subtitles: subtitles(project)
                    case .dubs: dubs(project)
                    default: overview(project)
                    }
                }
                .frame(maxWidth: 900, alignment: .leading)
                .padding(28)
                .frame(maxWidth: .infinity, alignment: .topLeading)
            } else {
                ContentUnavailableView("Open a Project", systemImage: "folder", description: Text("Choose a project in the library."))
            }
        }
        .navigationTitle(state.currentProject?.displayName ?? "Project")
    }

    private func header(_ project: ProjectSummary) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(project.displayName).font(.largeTitle.bold())
            Text(project.source).font(.callout).foregroundStyle(.secondary).textSelection(.enabled)
            HStack {
                Label("\(project.dubs.count) dubs", systemImage: "waveform")
                Label("\(project.subtitles.count) subtitle sets", systemImage: "captions.bubble")
                if project.status == "running" {
                    Label(project.stageTitle, systemImage: "hourglass")
                }
            }
            .font(.caption).foregroundStyle(.secondary)
        }
    }

    private func overview(_ project: ProjectSummary) -> some View {
        VStack(alignment: .leading, spacing: 20) {
            GroupBox("Source") {
                VStack(alignment: .leading, spacing: 8) {
                    LabeledContent("Series", value: project.seriesID.isEmpty ? "—" : project.seriesID)
                    Text(project.source).textSelection(.enabled)
                    if let path = project.artifacts["source_video"] {
                        ArtifactLink(title: "Original video", path: path)
                    }
                }.frame(maxWidth: .infinity, alignment: .leading)
            }
            HStack {
                Button("View Subtitles") { state.selection = .subtitles }
                Button("View Dubs") { state.selection = .dubs }
                Spacer()
                Button("New Dub", systemImage: "waveform.badge.plus") { state.selection = .newDub }
                    .buttonStyle(.borderedProminent)
            }
            subtitles(project)
            dubs(project)
        }
    }

    private func media(_ project: ProjectSummary) -> some View {
        GroupBox("Source / Media") {
            VStack(alignment: .leading, spacing: 14) {
                LabeledContent("Original source", value: project.source)
                LabeledContent("Output folder", value: project.outputDir)
                if let path = project.artifacts["source_video"] {
                    ArtifactLink(title: "Cached original video", path: path)
                } else {
                    Text("The original video will be downloaded or resolved when processing starts.")
                        .foregroundStyle(.secondary)
                }
                Button("Reveal Project Files", systemImage: "folder") {
                    NSWorkspace.shared.open(URL(fileURLWithPath: project.outputDir))
                }
            }.frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private func subtitles(_ project: ProjectSummary) -> some View {
        GroupBox("Subtitles and Transcripts") {
            VStack(alignment: .leading, spacing: 14) {
                if project.subtitles.isEmpty {
                    Text("No subtitles yet. Generate subtitles on their own or create a dub. Files appear here as soon as translation finishes.")
                        .foregroundStyle(.secondary)
                }
                ForEach(project.subtitles) { set in
                    VStack(alignment: .leading, spacing: 7) {
                        Label("\(set.language.uppercased()) · \(set.createdAt)", systemImage: "captions.bubble")
                            .font(.headline)
                        ForEach(set.artifacts.keys.sorted(), id: \.self) { kind in
                            if let path = set.artifacts[kind] {
                                ArtifactLink(title: kind.replacingOccurrences(of: "_", with: " ").capitalized, path: path)
                            }
                        }
                    }
                    Divider()
                }
                HStack {
                    Spacer()
                    Button("Generate Subtitles", systemImage: "text.badge.plus") {
                        state.outputMode = .subtitles
                        state.selection = .newDub
                    }
                }
            }.frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private func dubs(_ project: ProjectSummary) -> some View {
        GroupBox("Dub Versions") {
            VStack(alignment: .leading, spacing: 12) {
                if project.dubs.isEmpty {
                    Text("No dub versions yet. A new dub will keep its own video, subtitles and settings.")
                        .foregroundStyle(.secondary)
                }
                ForEach(project.dubs) { dub in
                    Button {
                        state.selectDub(dub)
                    } label: {
                        HStack {
                            Image(systemName: dub.status == "completed" ? "checkmark.circle.fill" : "waveform.circle")
                                .foregroundStyle(dub.status == "completed" ? Color.green : Color.secondary)
                            VStack(alignment: .leading, spacing: 3) {
                                Text(dub.title).fontWeight(.medium)
                                Text("\(dub.language.uppercased()) · \(dub.config["tts_engine"] as? String ?? "Voice pending") · \(dub.createdAt)")
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                            Spacer()
                            Text(dub.status.capitalized).font(.caption).foregroundStyle(.secondary)
                            Image(systemName: "chevron.right").font(.caption).foregroundStyle(.tertiary)
                        }.contentShape(Rectangle())
                    }.buttonStyle(.plain)
                    Divider()
                }
                HStack {
                    Spacer()
                    Button("New Dub", systemImage: "waveform.badge.plus") {
                        state.outputMode = .dub
                        state.dubName = ""
                        state.selection = .newDub
                    }
                }
            }.frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

struct ArtifactLink: View {
    let title: String
    let path: String

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: path.hasSuffix(".srt") || path.hasSuffix(".vtt") ? "captions.bubble" : "doc")
                .foregroundStyle(.secondary)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).fontWeight(.medium)
                Text(path).font(.caption.monospaced()).foregroundStyle(.secondary)
                    .lineLimit(2).textSelection(.enabled)
            }
            Spacer()
            Button { NSWorkspace.shared.open(URL(fileURLWithPath: path)) } label: {
                Image(systemName: "arrow.up.right.square")
            }.help("Open")
            Button { exportFile(path) } label: {
                Image(systemName: "square.and.arrow.up")
            }.help("Export a copy…")
        }
    }
}

func exportFile(_ path: String) {
    let source = URL(fileURLWithPath: path)
    guard FileManager.default.fileExists(atPath: source.path) else { return }
    let panel = NSSavePanel()
    panel.nameFieldStringValue = source.lastPathComponent
    guard panel.runModal() == .OK, let destination = panel.url else { return }
    do {
        if FileManager.default.fileExists(atPath: destination.path) {
            try FileManager.default.removeItem(at: destination)
        }
        try FileManager.default.copyItem(at: source, to: destination)
    } catch {
        NSAlert(error: error).runModal()
    }
}
