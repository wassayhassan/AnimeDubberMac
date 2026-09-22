import SwiftUI

struct RootView: View {
    @EnvironmentObject private var state: AppState

    var body: some View {
        NavigationSplitView {
            List(selection: $state.selection) {
                ForEach(SidebarDestination.allCases) { destination in
                    Label(destination.title, systemImage: destination.symbol)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .contentShape(Rectangle())
                        .tag(destination)
                }
            }
            .listStyle(.sidebar)
            .navigationTitle("AnimeDubber")
            .navigationSplitViewColumnWidth(min: 180, ideal: 205, max: 260)
        } detail: {
            detail
                .toolbar {
                    ToolbarItemGroup(placement: .primaryAction) {
                        backendBadge

                        Button {
                            state.runSystemCheck()
                        } label: {
                            Label("System Check", systemImage: "stethoscope")
                        }
                    }
                }
                .safeAreaInset(edge: .bottom, spacing: 0) {
                    StatusBarView()
                }
        }
        .sheet(isPresented: $state.showingSystemCheck) {
            SystemCheckSheet()
                .environmentObject(state)
        }
        .onChange(of: state.settingsSnapshot) { _, _ in
            state.savePreferences()
        }
    }

    @ViewBuilder
    private var detail: some View {
        switch state.selection ?? .newDub {
        case .newDub:
            NewDubView()
        case .projects:
            ProjectsView()
        case .characters:
            CharactersView()
        case .activity:
            ActivityView()
        case .settings:
            SettingsView()
        }
    }

    private var backendBadge: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(state.backendState.color)
                .frame(width: 8, height: 8)
            Text(state.backendState.label)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 5)
        .background(.quaternary, in: Capsule())
        .help(backendHelp)
    }

    private var backendHelp: String {
        switch state.backendState {
        case .failed(let message): message
        default: state.backendState.label
        }
    }
}

private struct SystemCheckSheet: View {
    @EnvironmentObject private var state: AppState
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("System Check")
                        .font(.title2.bold())
                    Text("Backend tools and local providers")
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Button("Done") { dismiss() }
                    .keyboardShortcut(.defaultAction)
            }

            List(state.systemCheckItems) { item in
                HStack(alignment: .top, spacing: 10) {
                    Image(systemName: item.ok ? "checkmark.circle.fill" : "xmark.circle.fill")
                        .foregroundStyle(item.ok ? .green : .red)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(item.name)
                            .fontWeight(.medium)
                        Text(item.detail)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .textSelection(.enabled)
                    }
                }
                .padding(.vertical, 3)
            }
        }
        .padding(22)
        .frame(width: 560, height: 430)
    }
}
