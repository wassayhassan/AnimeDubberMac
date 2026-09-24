import SwiftUI

struct NewProjectView: View {
    @EnvironmentObject private var state: AppState
    @State private var detailsExpanded = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                Label("Dub a Video", systemImage: "waveform.badge.plus")
                    .font(.largeTitle.bold())
                Text("Add a video, choose a language, and we'll make the dub and subtitles automatically.")
                    .foregroundStyle(.secondary)

                Form {
                    Section("Video") {
                        HStack {
                            TextField("Paste a video page link or choose a file", text: $state.source)
                            Button("Choose File…") { state.chooseSourceFile() }
                        }
                        Text("You can also drop a video file here. Use the video's page link, not a temporary playback URL.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    Section("Dub language") {
                        Picker("Language", selection: $state.targetLanguage) {
                            Text("English").tag("en")
                            Text("Spanish · voice setup required").tag("es")
                            Text("French · voice setup required").tag("fr")
                            Text("German · voice setup required").tag("de")
                            Text("Japanese · voice setup required").tag("ja")
                        }
                    }
                    DisclosureGroup("Project details (optional)", isExpanded: $detailsExpanded) {
                        TextField("Project name", text: $state.projectName)
                        TextField("Series identifier", text: $state.seriesID)
                        HStack {
                            TextField("Output folder", text: $state.outputFolder)
                            Button("Choose…") { state.chooseOutputFolder() }
                        }
                    }
                }
                .formStyle(.grouped)
                .onDrop(of: ["public.file-url"], isTargeted: nil) { providers in
                    guard let provider = providers.first else { return false }
                    _ = provider.loadObject(ofClass: URL.self) { url, _ in
                        if let url, url.isFileURL {
                            DispatchQueue.main.async { state.source = url.path }
                        }
                    }
                    return true
                }

                if !state.jobIssue.isEmpty {
                    Label(state.jobIssue, systemImage: "exclamationmark.triangle")
                        .foregroundStyle(.orange)
                } else if let issue = state.quickStartProblem, !state.source.isEmpty {
                    Label(issue, systemImage: "info.circle")
                        .foregroundStyle(.secondary)
                }
                if let issue = state.quickStartProblem,
                   issue.contains("Settings") || issue.contains("translation provider") || issue.contains("model file") {
                    Button("Open Processing Settings") {
                        state.settingsShowProviders = true
                        state.selection = .settings
                    }
                }
                if !state.canQuickStart && !state.startPending && !state.jobStartPending && state.activeJobID == nil {
                    Button("Reconnect Processing Service") { state.connectBackend() }
                }

                HStack {
                    Button("Create Project Only") { state.createProject() }
                        .disabled(state.source.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    Spacer()
                    Button("Dub Video") { state.quickStart() }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.large)
                        .disabled(!state.canQuickStart || state.quickStartProblem != nil)
                }
            }
            .frame(maxWidth: 760, alignment: .leading)
            .padding(28)
            .frame(maxWidth: .infinity, alignment: .topLeading)
        }
        .navigationTitle("Dub a Video")
    }
}
