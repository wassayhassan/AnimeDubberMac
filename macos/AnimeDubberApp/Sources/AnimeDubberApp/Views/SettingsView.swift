import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var state: AppState

    var body: some View {
        Form {
            Section("Backend") {
                LabeledContent("Status") {
                    HStack(spacing: 6) {
                        Circle()
                            .fill(state.backendState.color)
                            .frame(width: 8, height: 8)
                        Text(state.backendState.label)
                    }
                }

                Button("Run System Check") {
                    state.runSystemCheck()
                }
            }

            Section("Defaults") {
                Toggle("Resume cached work", isOn: $state.resumeCachedWork)
                Toggle("Detect separate speakers", isOn: $state.detectCharacters)
                Toggle("Background ducking", isOn: $state.backgroundDucking)
            }

            Section("v4 Migration") {
                Text("API keys will move to Keychain and cross-platform providers will be configured here as the provider layer lands.")
                    .foregroundStyle(.secondary)
            }
        }
        .formStyle(.grouped)
        .padding()
        .navigationTitle("Settings")
    }
}
