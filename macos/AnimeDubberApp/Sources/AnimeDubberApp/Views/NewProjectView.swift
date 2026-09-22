import SwiftUI

struct NewProjectView: View {
    @EnvironmentObject private var state: AppState

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                Label("New Project", systemImage: "folder.badge.plus")
                    .font(.largeTitle.bold())
                Text("A project keeps one original video, its subtitles, and every dub version together.")
                    .foregroundStyle(.secondary)

                Form {
                    Section("Original video") {
                        HStack {
                            TextField("YouTube URL or local video path", text: $state.source)
                            Button("Choose File…") { state.chooseSourceFile() }
                        }
                    }
                    Section("Workspace") {
                        TextField("Project name (optional)", text: $state.projectName)
                        TextField("Series identifier (optional)", text: $state.seriesID)
                        HStack {
                            TextField("Output folder", text: $state.outputFolder)
                            Button("Choose…") { state.chooseOutputFolder() }
                        }
                    }
                }
                .formStyle(.grouped)

                HStack {
                    Spacer()
                    Button("Create Project") { state.createProject() }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.large)
                        .disabled(state.source.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
            .frame(maxWidth: 760, alignment: .leading)
            .padding(28)
            .frame(maxWidth: .infinity, alignment: .topLeading)
        }
        .navigationTitle("New Project")
    }
}
