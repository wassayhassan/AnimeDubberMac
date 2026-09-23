import SwiftUI

struct NewDubView: View {
    @EnvironmentObject private var state: AppState
    @State private var advancedExpanded = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                header
                identitySection
                pipelineSection
                actions
            }
            .frame(maxWidth: 860, alignment: .leading)
            .padding(28)
            .frame(maxWidth: .infinity, alignment: .topLeading)
        }
        .navigationTitle("New Dub")
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(state.outputMode == .subtitles ? "Generate Subtitles" : "Create Dub Version")
                .font(.largeTitle.bold())
            Text("\(state.currentProject?.displayName ?? "Open a project") · \(state.source)")
                .font(.title3)
                .foregroundStyle(.secondary)
        }
    }

    private var identitySection: some View {
        GroupBox("This Version") {
            Grid(alignment: .leading, horizontalSpacing: 16, verticalSpacing: 12) {
                GridRow {
                    Text("Project")
                        .foregroundStyle(.secondary)
                    Text(state.currentProject?.displayName ?? "No project selected")
                }
                GridRow {
                    Text("Create")
                        .foregroundStyle(.secondary)
                    Picker("Create", selection: $state.outputMode) {
                        ForEach(OutputMode.allCases) { mode in Text(mode.title).tag(mode) }
                    }
                    .labelsHidden()
                }
                GridRow {
                    Text("Language")
                        .foregroundStyle(.secondary)
                    Picker("Language", selection: $state.targetLanguage) {
                        Text("English").tag("en")
                        Text("Spanish").tag("es")
                        Text("French").tag("fr")
                        Text("German").tag("de")
                        Text("Japanese").tag("ja")
                    }.labelsHidden()
                }
                if state.outputMode == .dub {
                    GridRow {
                        Text("Dub name").foregroundStyle(.secondary)
                        TextField("Optional, e.g. English — Chatterbox", text: $state.dubName)
                    }
                }
            }
            .padding(.top, 4)
        }
    }

    private var pipelineSection: some View {
        GroupBox("Pipeline") {
            VStack(spacing: 0) {
                settingRow("Speech recognition") {
                    Picker("Speech recognition", selection: $state.asrProvider) {
                        ForEach(ASRProvider.allCases) { item in
                            Text(item.title).tag(item)
                        }
                    }
                    .labelsHidden()
                    .frame(width: 240)
                }

                Divider()

                settingRow("Translation") {
                    Picker("Translation", selection: $state.translationProvider) {
                        ForEach(TranslationProvider.allCases) { item in
                            Text(item.title).tag(item)
                        }
                    }
                    .labelsHidden()
                    .frame(width: 240)
                }

                Divider()

                settingRow("Voices") {
                    Picker("Voices", selection: $state.voiceProvider) {
                        ForEach(VoiceProvider.allCases) { item in
                            Text(item.title).tag(item)
                        }
                    }
                    .labelsHidden()
                    .frame(width: 240)
                }

                Divider()

                settingRow("Characters") {
                    Toggle("Detect separate speakers", isOn: $state.detectCharacters)
                }

                if state.outputMode == .dub {
                    Divider()
                    settingRow("Subtitle review") {
                        Toggle("Review flagged lines before voices", isOn: $state.reviewBeforeDub)
                    }
                    if state.reviewBeforeDub {
                        Text("After subtitles are saved, larger local models check priority lines. The dub pauses so you can inspect their suggestions in Dub Details and approve or edit them. This downloads models on first use and adds processing time.")
                            .font(.caption).foregroundStyle(.secondary)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        if state.translationProvider == .whisper {
                            Text("Choose Local LLM or Ollama translation for line-aligned review.")
                                .font(.caption).foregroundStyle(.orange)
                        }
                    }
                }

                if state.detectCharacters && state.outputMode == .dub && state.targetLanguage == "en" &&
                    (state.voiceProvider == .chatterbox || state.voiceProvider == .auto) {
                    settingRow("Source voices") {
                        Toggle("Choose character voice clips automatically", isOn: $state.autoSourceVoices)
                    }
                    Text("Analyze Characters first to check each source clip. A character without a usable clip gets a Kokoro or macOS voice; source identity and child-like tone cannot be guaranteed without a clean reference.")
                        .font(.caption).foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }

                if state.targetLanguage != "en" {
                    Text("Other languages use an LLM or Ollama for translation. Dubbing currently requires an ElevenLabs multilingual voice; subtitles work without one.")
                        .font(.caption).foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.vertical, 8)
                }

                Divider()

                DisclosureGroup("Advanced", isExpanded: $advancedExpanded) {
                    advancedSettings
                        .padding(.top, 10)
                }
                .padding(.vertical, 11)
            }
            .padding(.horizontal, 2)
        }
    }

    private var advancedSettings: some View {
        Grid(alignment: .leading, horizontalSpacing: 16, verticalSpacing: 12) {
            GridRow {
                Text("Speaker backend")
                    .foregroundStyle(.secondary)
                Picker("Speaker backend", selection: $state.speakerBackend) {
                    Text("Auto").tag("auto")
                    Text("ECAPA").tag("ecapa")
                    Text("Acoustic").tag("acoustic")
                }
                .labelsHidden()
                .frame(width: 180)
            }

            GridRow {
                Text("Maximum speakers")
                    .foregroundStyle(.secondary)
                Stepper(value: $state.maxSpeakers, in: 2...30) {
                    Text("\(state.maxSpeakers)")
                        .monospacedDigit()
                }
            }

            GridRow {
                Text("Speaker threshold")
                    .foregroundStyle(.secondary)
                HStack {
                    TextField("0", value: $state.speakerThreshold, format: .number)
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 90)
                    Text("0 = automatic")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            GridRow {
                Text("Music / SFX")
                    .foregroundStyle(.secondary)
                HStack {
                    Slider(value: $state.backgroundVolume, in: 0.2...2.0, step: 0.05)
                    Text(state.backgroundVolume.formatted(.number.precision(.fractionLength(2))))
                        .monospacedDigit()
                        .frame(width: 42)
                }
            }

            GridRow {
                Text("Dub voice")
                    .foregroundStyle(.secondary)
                HStack {
                    Slider(value: $state.dubVolume, in: 0.2...2.0, step: 0.05)
                    Text(state.dubVolume.formatted(.number.precision(.fractionLength(2))))
                        .monospacedDigit()
                        .frame(width: 42)
                }
            }

            GridRow {
                Text("")
                Toggle("Duck background under dialogue", isOn: $state.backgroundDucking)
            }

            GridRow {
                Text("Series context")
                    .foregroundStyle(.secondary)
                TextEditor(text: $state.seriesContext)
                    .font(.body)
                    .frame(minHeight: 70, maxHeight: 100)
                    .overlay {
                        RoundedRectangle(cornerRadius: 6)
                            .stroke(.separator, lineWidth: 1)
                    }
            }
        }
    }

    private var actions: some View {
        HStack {
            Spacer()

            Button("Analyze Characters") {
                state.startJob(analysis: true)
            }
            .disabled(!state.canStartJob)

            Button(state.outputMode == .subtitles ? "Generate Subtitles" : "Generate Dub") {
                state.startJob(analysis: false)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(!state.canStartJob || (state.reviewBeforeDub && state.outputMode == .dub && state.translationProvider == .whisper) || (state.targetLanguage != "en" &&
                (state.translationProvider == .whisper || (state.outputMode == .dub && state.voiceProvider != .elevenlabs))))
        }
    }

    private func settingRow<Content: View>(_ title: String, @ViewBuilder content: () -> Content) -> some View {
        HStack {
            Text(title)
                .foregroundStyle(.secondary)
            Spacer()
            content()
        }
        .padding(.vertical, 11)
    }
}
