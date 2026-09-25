import SwiftUI

struct ActivityDrawer: View {
    @EnvironmentObject private var state: AppState
    @State private var tab = "Progress"

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Picker("Activity view", selection: $tab) {
                    Text("Progress").tag("Progress")
                    Text("Diagnostics").tag("Diagnostics")
                }
                .pickerStyle(.segmented)
                .frame(width: 220)

                Spacer()

                if !state.activity.isEmpty {
                    Button("Clear") {
                        state.activity.removeAll()
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(10)

            Divider()

            if tab == "Progress" {
                activityList
            } else {
                diagnostics
            }
        }
        .background(.background)
    }

    private var activityList: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 8) {
                if state.activity.isEmpty {
                    ContentUnavailableView(
                        "No Activity Yet",
                        systemImage: "waveform",
                        description: Text("Processing stages, warnings, and output files will appear here.")
                    )
                    .padding(.top, 24)
                } else {
                    ForEach(state.activity.suffix(100)) { entry in
                        HStack(alignment: .top, spacing: 9) {
                            Image(systemName: entry.symbol)
                                .foregroundStyle(entry.tint)
                                .font(.caption)
                                .padding(.top, 3)

                            Text(entry.message)
                                .font(.system(.caption, design: .monospaced))
                                .textSelection(.enabled)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                }
            }
            .padding(12)
        }
    }

    private var diagnostics: some View {
        ScrollView {
            Text(state.backendDiagnostics.isEmpty ? "No backend diagnostics." : state.backendDiagnostics)
                .font(.system(.caption, design: .monospaced))
                .textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .topLeading)
                .padding(12)
        }
    }
}
