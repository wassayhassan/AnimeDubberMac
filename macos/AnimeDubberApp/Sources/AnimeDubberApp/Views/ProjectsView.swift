import SwiftUI

struct ProjectsView: View {
    @EnvironmentObject private var state: AppState

    var body: some View {
        Group {
            if state.projects.isEmpty {
                ContentUnavailableView {
                    Label("No Projects Yet", systemImage: "square.stack.3d.up")
                } description: {
                    Text("Start a project with a video or open one created by the CLI.")
                } actions: {
                    Button("New Project") { state.newProject() }
                        .buttonStyle(.borderedProminent)
                }
            } else {
                VStack(spacing: 0) {
                    Table(state.projects, selection: $state.selectedProjectID) {
                        TableColumn("Project") { project in
                            VStack(alignment: .leading, spacing: 3) {
                                Text(project.displayName).fontWeight(.medium)
                                Text(project.source).font(.caption).foregroundStyle(.secondary).lineLimit(1)
                            }.padding(.vertical, 4)
                        }
                        TableColumn("Dubs") { project in
                            Text("\(project.dubs.count)").monospacedDigit()
                        }.width(65)
                        TableColumn("Subtitles") { project in
                            Text("\(project.subtitles.count)").monospacedDigit()
                        }.width(90)
                        TableColumn("Status") { project in
                            Text(project.statusLabel)
                        }.width(110)
                    }
                    HStack {
                        Text("Select a project to open its workspace.")
                            .font(.caption).foregroundStyle(.secondary)
                        Spacer()
                        Button("Open Project") {
                            if let project = state.currentProject { state.openProject(project) }
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(state.currentProject == nil)
                    }.padding(16)
                }
            }
        }
        .navigationTitle("Projects")
        .toolbar {
            Button { state.newProject() } label: {
                Label("New Project", systemImage: "folder.badge.plus")
            }
            Button { state.refreshProjects() } label: {
                Label("Refresh", systemImage: "arrow.clockwise")
            }
        }
        .task { state.refreshProjects() }
    }
}
