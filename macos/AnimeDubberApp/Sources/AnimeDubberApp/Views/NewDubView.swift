import SwiftUI

struct NewDubView: View {
    @EnvironmentObject private var state: AppState
    @State private var advancedExpanded = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                header
                sourceSection
                projectSection
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
            Text("Create English Dub")
                .font(.largeTitle.bold())
            Text("Choose a source, review the pipeline, then let AnimeDubber handle the long-running work.")
                .font(.title3)
                .foregroundStyle(.secondary)
        }
    }

    private var sourceSection: some View {
        GroupBox("Source") {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 10) {
                    TextField("YouTube URL or local video path", text: $state.source)
                        .textFieldStyle(.roundedBorder)

                    Button("Choose File…") {
                        state.chooseSourceFile()
                    }
                }

                Text("Paste a YouTube URL or select a local video.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .padding(.top, 4)
        }
    }

    private var projectSection: some View {
        GroupBox("Project") {
            Grid(alignment: .leading, horizontalSpacing: 16, verticalSpacing: 12) {
                GridRow {
                    Text("Series ID")
                        .foregroundStyle(.secondary)
                    TextField("Optional series identifier", text: $state.seriesID)
                        .textFieldStyle(.roundedBorder)
                }

                GridRow {
                    Text("Output folder")
                        .foregroundStyle(.secondary)
                    HStack {
                        TextField("Output folder", text: $state.outputFolder)
                            .textFieldStyle(.roundedBorder)
                        Button("Choose…") {
                            state.chooseOutputFolder()
                        }
                    }
                }

                GridRow {
                    Text("")
                    Toggle("Resume cached work", isOn: $state.resumeCachedWork)
                }
            }
            .padding(.top, 4)
        }
    }

    private var pipelineSection: some View {
        GroupBox("Pipeline") {
            VStack(spacing: 0) {
                settingRow("Output") {
                    Picker("Output", selection: $state.outputMode) {
                        ForEach(OutputMode.allCases) { item in
                            Text(item.title).tag(item)
                        }
                    }
                    .labelsHidden()
                    .frame(width: 240)
                }

                Divider()

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
                Text("English voice")
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
                Toggle("Duck background under English dialogue", isOn: $state.backgroundDucking)
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

            Button("Generate Dub") {
                state.startJob(analysis: false)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(!state.canStartJob)
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
