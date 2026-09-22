import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var state: AppState
    @State private var selectedTab = "general"

    var body: some View {
        TabView(selection: $selectedTab) {
            general
                .tabItem { Label("General", systemImage: "slider.horizontal.3") }
                .tag("general")

            providers
                .tabItem { Label("Providers", systemImage: "cpu") }
                .tag("providers")

            backend
                .tabItem { Label("Backend", systemImage: "server.rack") }
                .tag("backend")
        }
        .padding(16)
        .onChange(of: state.settingsSnapshot) { _, _ in
            state.savePreferences()
        }
        .onDisappear {
            state.savePreferences()
        }
    }

    private var general: some View {
        Form {
            Section("Project Defaults") {
                LabeledContent("Output folder") {
                    HStack {
                        TextField("Output folder", text: $state.outputFolder)
                            .textFieldStyle(.roundedBorder)
                            .frame(minWidth: 300)
                        Button("Choose…") {
                            state.chooseOutputFolder()
                        }
                    }
                }

                LabeledContent("Series ID") {
                    TextField("Optional default series ID", text: $state.seriesID)
                        .textFieldStyle(.roundedBorder)
                        .frame(minWidth: 300)
                }

                Picker("Output", selection: $state.outputMode) {
                    ForEach(OutputMode.allCases) { item in
                        Text(item.title).tag(item)
                    }
                }

                Toggle("Resume cached work", isOn: $state.resumeCachedWork)
                Toggle("Detect separate speakers", isOn: $state.detectCharacters)
            }

            Section("Audio Defaults") {
                LabeledContent("Music / SFX") {
                    HStack {
                        Slider(value: $state.backgroundVolume, in: 0.2...2.0, step: 0.05)
                            .frame(width: 220)
                        Text(state.backgroundVolume.formatted(.number.precision(.fractionLength(2))))
                            .monospacedDigit()
                            .frame(width: 40)
                    }
                }

                LabeledContent("English voice") {
                    HStack {
                        Slider(value: $state.dubVolume, in: 0.2...2.0, step: 0.05)
                            .frame(width: 220)
                        Text(state.dubVolume.formatted(.number.precision(.fractionLength(2))))
                            .monospacedDigit()
                            .frame(width: 40)
                    }
                }

                Toggle("Duck background under English dialogue", isOn: $state.backgroundDucking)
            }
        }
        .formStyle(.grouped)
    }

    private var providers: some View {
        Form {
            Section("Speech Recognition") {
                Picker("ASR provider", selection: $state.asrProvider) {
                    ForEach(ASRProvider.allCases) { provider in
                        Text(provider.title).tag(provider)
                    }
                }

                if state.asrProvider == .fasterWhisper {
                    LabeledContent("Model") {
                        TextField("large-v3", text: $state.fasterWhisperModel)
                            .textFieldStyle(.roundedBorder)
                            .frame(width: 220)
                    }
                    Picker("Device", selection: $state.fasterWhisperDevice) {
                        Text("Automatic").tag("auto")
                        Text("CPU").tag("cpu")
                        Text("CUDA").tag("cuda")
                    }
                    LabeledContent("Compute type") {
                        TextField("auto", text: $state.fasterWhisperComputeType)
                            .textFieldStyle(.roundedBorder)
                            .frame(width: 160)
                    }
                }
            }

            Section("Translation") {
                Picker("Translation provider", selection: $state.translationProvider) {
                    ForEach(TranslationProvider.allCases) { provider in
                        Text(provider.title).tag(provider)
                    }
                }

                if state.translationProvider == .ollama {
                    LabeledContent("Ollama URL") {
                        TextField("http://127.0.0.1:11434", text: $state.ollamaURL)
                            .textFieldStyle(.roundedBorder)
                            .frame(width: 280)
                    }
                    LabeledContent("Model") {
                        TextField("qwen3:4b", text: $state.ollamaModel)
                            .textFieldStyle(.roundedBorder)
                            .frame(width: 220)
                    }
                }
            }

            Section("English Voice") {
                Picker("TTS provider", selection: $state.voiceProvider) {
                    ForEach(VoiceProvider.allCases) { provider in
                        Text(provider.title).tag(provider)
                    }
                }

                if state.voiceProvider == .macos || state.voiceProvider == .auto {
                    LabeledContent("Fallback voice") {
                        Picker("Fallback voice", selection: $state.fallbackVoice) {
                            Text("System default").tag("")
                            ForEach(state.installedVoices, id: \.self) { voice in
                                Text(voice).tag(voice)
                            }
                        }
                        .labelsHidden()
                        .frame(width: 230)
                    }
                }

                LabeledContent("Speaking rate") {
                    Stepper(value: $state.ttsRate, in: 80...450, step: 5) {
                        Text("\(state.ttsRate)")
                            .monospacedDigit()
                    }
                }

                if state.voiceProvider == .piper {
                    LabeledContent("Piper model") {
                        HStack {
                            TextField("Path to .onnx voice", text: $state.piperModel)
                                .textFieldStyle(.roundedBorder)
                                .frame(minWidth: 280)
                            Button("Choose…") {
                                state.choosePiperModel()
                            }
                        }
                    }
                    LabeledContent("Speaker ID") {
                        Stepper(value: $state.piperSpeaker, in: -1...64) {
                            Text(state.piperSpeaker < 0 ? "Default" : "\(state.piperSpeaker)")
                                .monospacedDigit()
                        }
                    }
                    Text("Piper requires a compatible .onnx voice model. -1 uses the model's default speaker.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                if state.voiceProvider == .elevenlabs {
                    LabeledContent("API key") {
                        SecureField("ElevenLabs API key", text: $state.elevenLabsAPIKey)
                            .textFieldStyle(.roundedBorder)
                            .frame(minWidth: 300)
                    }

                    LabeledContent("Voice ID") {
                        TextField("Voice ID", text: $state.elevenLabsVoiceID)
                            .textFieldStyle(.roundedBorder)
                            .frame(minWidth: 300)
                    }

                    HStack {
                        Text("The API key is stored in macOS Keychain, not UserDefaults or project files.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Spacer()
                        Button("Save API Key") {
                            state.saveSecrets()
                        }
                    }

                    if !state.credentialStatus.isEmpty {
                        Text(state.credentialStatus)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
        .formStyle(.grouped)
    }

    private var backend: some View {
        Form {
            Section("Backend") {
                LabeledContent("Status") {
                    HStack(spacing: 7) {
                        Circle()
                            .fill(state.backendState.color)
                            .frame(width: 8, height: 8)
                        Text(state.backendState.label)
                    }
                }

                Button("Run System Check") {
                    state.runSystemCheck()
                }

                Text("Installed app builds launch the bundled Python backend automatically. Development builds continue to use the repository backend.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Section("Diagnostics") {
                Text(state.backendDiagnostics.isEmpty ? "No backend diagnostics." : state.backendDiagnostics)
                    .font(.system(.caption, design: .monospaced))
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .lineLimit(12)

                if !state.backendDiagnostics.isEmpty {
                    Button("Clear Diagnostics") {
                        state.backendDiagnostics = ""
                    }
                }
            }
        }
        .formStyle(.grouped)
    }
}
