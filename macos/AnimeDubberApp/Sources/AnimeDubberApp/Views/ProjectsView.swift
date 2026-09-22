import SwiftUI

struct ProjectsView: View {
    @EnvironmentObject private var state: AppState

    private var selectedProject: ProjectSummary? {
        guard let id = state.selectedProjectID else { return nil }
        return state.projects.first(where: { $0.id == id })
    }

    var body: some View {
        Group {
            if state.projects.isEmpty {
                ContentUnavailableView {
                    Label("No Projects Yet", systemImage: "square.stack.3d.up")
                } description: {
                    Text("Completed and resumable jobs in the current output folder will appear here.")
                } actions: {
                    Button("Refresh") {
                        state.refreshProjects()
                    }
                }
            } else {
                Table(state.projects, selection: $state.selectedProjectID) {
                    TableColumn("Project") { project in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(project.displayName)
                                .fontWeight(.medium)
                                .lineLimit(1)
                            Text(project.source)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .lineLimit(1)
                        }
                        .padding(.vertical, 3)
                    }

                    TableColumn("Status") { project in
                        HStack(spacing: 6) {
                            Circle()
                                .fill(statusColor(project.status))
                                .frame(width: 7, height: 7)
                            Text(project.statusLabel)
                        }
                    }
                    .width(min: 110, ideal: 130)

                    TableColumn("Stage") { project in
                        Text(project.stageTitle.isEmpty ? project.stage : project.stageTitle)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    }
                    .width(min: 120, ideal: 170)

                    TableColumn("Updated") { project in
                        Text(shortDate(project.updatedAt))
                            .foregroundStyle(.secondary)
                    }
                    .width(min: 120, ideal: 145)
                }
            }
        }
        .navigationTitle("Projects")
        .toolbar {
            Button {
                state.refreshProjects()
            } label: {
                Label("Refresh Projects", systemImage: "arrow.clockwise")
            }
        }
        .inspector(isPresented: Binding(
            get: { selectedProject != nil },
            set: { if !$0 { state.selectedProjectID = nil } }
        )) {
            if let project = selectedProject {
                ProjectInspector(project: project)
                    .environmentObject(state)
                    .inspectorColumnWidth(min: 280, ideal: 330, max: 420)
            }
        }
        .task {
            state.refreshProjects()
        }
    }

    private func statusColor(_ status: String) -> Color {
        switch status {
        case "completed": .green
        case "running", "queued": .blue
        case "failed": .red
        case "cancelled": .secondary
        default: .orange
        }
    }

    private func shortDate(_ value: String) -> String {
        guard !value.isEmpty else { return "—" }
        let formatter = ISO8601DateFormatter()
        guard let date = formatter.date(from: value) else { return value }
        return date.formatted(date: .abbreviated, time: .shortened)
    }
}

private struct ProjectInspector: View {
    @EnvironmentObject private var state: AppState
    let project: ProjectSummary

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                VStack(alignment: .leading, spacing: 5) {
                    Text(project.displayName)
                        .font(.title2.bold())
                    Text(project.id)
                        .font(.caption.monospaced())
                        .foregroundStyle(.secondary)
                        .textSelection(.enabled)
                }

                GroupBox("Status") {
                    VStack(alignment: .leading, spacing: 10) {
                        LabeledContent("State", value: project.statusLabel)
                        LabeledContent("Stage", value: project.stageTitle.isEmpty ? project.stage : project.stageTitle)

                        if let progress = project.progress {
                            ProgressView(value: progress)
                            Text(progress, format: .percent.precision(.fractionLength(0)))
                                .font(.caption.monospacedDigit())
                                .foregroundStyle(.secondary)
                        }

                        if project.warningCount > 0 {
                            Label("\(project.warningCount) warning\(project.warningCount == 1 ? "" : "s")", systemImage: "exclamationmark.triangle")
                                .foregroundStyle(.orange)
                        }

                        if let error = project.lastError, !error.isEmpty {
                            Text(error)
                                .font(.caption)
                                .foregroundStyle(.red)
                                .textSelection(.enabled)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }

                GroupBox("Project") {
                    VStack(alignment: .leading, spacing: 10) {
                        LabeledContent("Series", value: project.seriesID.isEmpty ? "—" : project.seriesID)

                        VStack(alignment: .leading, spacing: 3) {
                            Text("Source")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            Text(project.source)
                                .font(.caption.monospaced())
                                .textSelection(.enabled)
                        }

                        VStack(alignment: .leading, spacing: 3) {
                            Text("Output folder")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            Text(project.outputDir)
                                .font(.caption.monospaced())
                                .textSelection(.enabled)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }

                GroupBox("Outputs") {
                    VStack(alignment: .leading, spacing: 8) {
                        if project.artifacts.isEmpty {
                            Text("No output artifacts recorded yet.")
                                .foregroundStyle(.secondary)
                        } else {
                            ForEach(project.artifacts.keys.sorted(), id: \.self) { key in
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(key.replacingOccurrences(of: "_", with: " ").capitalized)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                    Text(project.artifacts[key] ?? "")
                                        .font(.caption.monospaced())
                                        .lineLimit(2)
                                        .textSelection(.enabled)
                                }
                            }
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }

                VStack(spacing: 8) {
                    Button("Use These Project Settings") {
                        state.useProject(project)
                    }
                    .frame(maxWidth: .infinity)

                    Button("Reveal Output in Finder") {
                        state.openProjectOutput(project)
                    }
                    .frame(maxWidth: .infinity)
                    .disabled(project.artifacts.isEmpty)
                }
            }
            .padding(18)
        }
    }
}
