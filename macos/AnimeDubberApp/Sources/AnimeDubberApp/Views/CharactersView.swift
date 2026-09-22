import SwiftUI

struct CharactersView: View {
    @EnvironmentObject private var state: AppState

    var body: some View {
        VStack(spacing: 0) {
            mapToolbar
            Divider()

            if state.characterMaps.isEmpty {
                ContentUnavailableView {
                    Label("No Character Analysis Yet", systemImage: "person.2")
                } description: {
                    Text("Run Analyze Characters for a video in the current output folder.")
                } actions: {
                    Button("Refresh") {
                        state.refreshCharacterMaps()
                    }
                }
            } else if state.characters.isEmpty {
                ProgressView("Loading characters…")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                Table(state.characters, selection: $state.selectedCharacterID) {
                    TableColumn("Character") { character in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(character.displayName)
                                .fontWeight(.medium)
                            Text(character.id)
                                .font(.caption.monospaced())
                                .foregroundStyle(.secondary)
                        }
                        .padding(.vertical, 3)
                    }

                    TableColumn("Role") { character in
                        Text(character.role.capitalized)
                    }
                    .width(min: 90, ideal: 110)

                    TableColumn("Voice Engine") { character in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(character.ttsProvider == "inherit" ? "App Default" : character.ttsProvider.capitalized)
                            if character.ttsProvider == "kokoro", character.kokoroVoice != "auto" {
                                Text(character.kokoroVoice)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            } else if character.ttsProvider == "macos", !character.macosVoice.isEmpty {
                                Text(character.macosVoice)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                    .width(min: 120, ideal: 160)

                    TableColumn("Lines") { character in
                        Text("\(character.lineCount)")
                            .monospacedDigit()
                    }
                    .width(65)

                    TableColumn("Speech") { character in
                        Text(character.speakingShare, format: .percent.precision(.fractionLength(1)))
                            .monospacedDigit()
                    }
                    .width(80)
                }
            }
        }
        .navigationTitle("Characters")
        .toolbar {
            Button {
                state.refreshCharacterMaps()
            } label: {
                Label("Refresh Characters", systemImage: "arrow.clockwise")
            }
        }
        .inspector(isPresented: Binding(
            get: { state.selectedCharacterID != nil },
            set: { if !$0 { state.selectCharacter(nil) } }
        )) {
            CharacterInspector()
                .environmentObject(state)
                .inspectorColumnWidth(min: 320, ideal: 370, max: 460)
        }
        .onChange(of: state.selectedCharacterID) { _, newValue in
            state.selectCharacter(newValue)
        }
        .task {
            state.refreshCharacterMaps()
        }
    }

    private var mapToolbar: some View {
        HStack(spacing: 10) {
            Text("Character Map")
                .fontWeight(.medium)

            Picker("Character Map", selection: Binding(
                get: { state.selectedCharacterMapPath ?? "" },
                set: { newValue in
                    if !newValue.isEmpty {
                        state.loadCharacterMap(newValue)
                    }
                }
            )) {
                ForEach(state.characterMaps) { map in
                    Text("\(map.displayName) · \(map.characterCount) characters")
                        .tag(map.path)
                }
            }
            .labelsHidden()
            .frame(minWidth: 260, maxWidth: 420)

            Spacer()

            if let map = state.characterMaps.first(where: { $0.path == state.selectedCharacterMapPath }) {
                Text(map.speakerBackend.isEmpty ? "Speaker analysis" : map.speakerBackend)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.horizontal, 16)
        .frame(height: 46)
    }
}

private struct CharacterInspector: View {
    @EnvironmentObject private var state: AppState

    private let roles = ["lead", "major", "supporting", "minor"]
    private let voiceClasses = ["male", "female", "neutral"]
    private let ageGroups = ["child", "adult", "older"]
    private let engines = [
        ("inherit", "App Default"),
        ("auto", "Automatic · Best Local"),
        ("chatterbox", "Chatterbox Turbo"),
        ("kokoro", "Kokoro"),
        ("elevenlabs", "ElevenLabs"),
        ("macos", "macOS Voice"),
        ("piper", "Piper"),
    ]
    private let kokoroVoices = [
        "auto", "af_heart", "af_bella", "af_sarah", "af_sky",
        "am_adam", "am_michael", "bf_emma", "bf_isabella", "bm_george", "bm_lewis",
    ]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(state.characterDraft.displayName.isEmpty ? "Character" : state.characterDraft.displayName)
                        .font(.title2.bold())
                    if let id = state.selectedCharacterID {
                        Text(id)
                            .font(.caption.monospaced())
                            .foregroundStyle(.secondary)
                    }
                }

                GroupBox("Identity") {
                    Grid(alignment: .leading, horizontalSpacing: 12, verticalSpacing: 11) {
                        GridRow {
                            Text("Name")
                                .foregroundStyle(.secondary)
                            TextField("Character name", text: $state.characterDraft.displayName)
                        }

                        GridRow {
                            Text("Role")
                                .foregroundStyle(.secondary)
                            Picker("Role", selection: $state.characterDraft.role) {
                                ForEach(roles, id: \.self) { role in
                                    Text(role.capitalized).tag(role)
                                }
                            }
                            .labelsHidden()
                        }

                        GridRow {
                            Text("Voice type")
                                .foregroundStyle(.secondary)
                            Picker("Voice type", selection: $state.characterDraft.voiceClass) {
                                ForEach(voiceClasses, id: \.self) { value in
                                    Text(value.capitalized).tag(value)
                                }
                            }
                            .labelsHidden()
                        }

                        GridRow {
                            Text("Age")
                                .foregroundStyle(.secondary)
                            Picker("Age", selection: $state.characterDraft.ageGroup) {
                                ForEach(ageGroups, id: \.self) { value in
                                    Text(value.capitalized).tag(value)
                                }
                            }
                            .labelsHidden()
                        }
                    }
                    .padding(.top, 4)
                }

                GroupBox("English Voice") {
                    VStack(alignment: .leading, spacing: 12) {
                        Picker("Engine", selection: $state.characterDraft.ttsProvider) {
                            ForEach(engines, id: \.0) { engine in
                                Text(engine.1).tag(engine.0)
                            }
                        }

                        if state.characterDraft.ttsProvider == "inherit" {
                            Text("Uses the app default: \(state.voiceProvider.title)")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }

                        if usesChatterbox {
                            LabeledContent("Reference clip") {
                                HStack {
                                    TextField("Optional audio clip", text: $state.characterDraft.referenceAudio)
                                        .textFieldStyle(.roundedBorder)
                                    Button("Choose…") {
                                        state.chooseCharacterReference()
                                    }
                                    if !state.characterDraft.referenceAudio.isEmpty {
                                        Button("Clear") {
                                            state.characterDraft.referenceAudio = ""
                                        }
                                    }
                                }
                            }

                            LabeledContent("Expressiveness") {
                                HStack {
                                    Slider(value: $state.characterDraft.expressiveness, in: 0...1.5, step: 0.05)
                                    Text(state.characterDraft.expressiveness, format: .number.precision(.fractionLength(2)))
                                        .monospacedDigit()
                                        .frame(width: 44)
                                }
                            }

                            Text("Reference audio is optional and is only used when you explicitly select it. Use a voice you have permission to clone.")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }

                        if usesKokoro {
                            LabeledContent("Kokoro voice") {
                                Picker("Kokoro voice", selection: $state.characterDraft.kokoroVoice) {
                                    ForEach(kokoroVoices, id: \.self) { voice in
                                        Text(voice == "auto" ? "Automatic by character" : voice)
                                            .tag(voice)
                                    }
                                }
                                .labelsHidden()
                            }
                        }

                        if usesMacVoice {
                            HStack {
                                TextField("macOS voice", text: $state.characterDraft.macosVoice)

                                if !state.installedVoices.isEmpty {
                                    Menu {
                                        Button("Automatic") {
                                            state.characterDraft.macosVoice = ""
                                        }
                                        Divider()
                                        ForEach(state.installedVoices, id: \.self) { voice in
                                            Button(voice) {
                                                state.characterDraft.macosVoice = voice
                                            }
                                        }
                                    } label: {
                                        Image(systemName: "chevron.down")
                                    }
                                }
                            }
                        }

                        if state.characterDraft.ttsProvider == "elevenlabs" {
                            LabeledContent("Voice ID") {
                                TextField("Use app default if empty", text: $state.characterDraft.elevenLabsVoiceID)
                            }
                        }

                        LabeledContent("Rate") {
                            Stepper(value: $state.characterDraft.ttsRate, in: 80...450, step: 5) {
                                Text("\(state.characterDraft.ttsRate)")
                                    .monospacedDigit()
                            }
                        }

                        LabeledContent("Pitch") {
                            HStack {
                                Slider(value: $state.characterDraft.pitchSemitones, in: -8...8, step: 0.25)
                                Text(state.characterDraft.pitchSemitones, format: .number.precision(.fractionLength(2)))
                                    .monospacedDigit()
                                    .frame(width: 46)
                            }
                        }

                        LabeledContent("Gain") {
                            HStack {
                                Slider(value: $state.characterDraft.voiceGain, in: 0.4...2.0, step: 0.05)
                                Text(state.characterDraft.voiceGain, format: .number.precision(.fractionLength(2)))
                                    .monospacedDigit()
                                    .frame(width: 46)
                            }
                        }

                        Button {
                            state.previewSelectedVoice()
                        } label: {
                            Label("Preview Voice", systemImage: "speaker.wave.2")
                        }
                    }
                    .padding(.top, 4)
                }

                GroupBox("Notes") {
                    TextEditor(text: $state.characterDraft.notes)
                        .frame(minHeight: 70)
                }

                HStack {
                    Text(state.characterSaveMessage)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Button("Save") {
                        state.saveSelectedCharacter()
                    }
                    .buttonStyle(.borderedProminent)
                }
            }
            .padding(18)
        }
    }

    private var usesChatterbox: Bool {
        state.characterDraft.ttsProvider == "chatterbox"
            || state.characterDraft.ttsProvider == "auto"
            || (state.characterDraft.ttsProvider == "inherit"
                && (state.voiceProvider == .chatterbox || state.voiceProvider == .auto))
    }

    private var usesKokoro: Bool {
        state.characterDraft.ttsProvider == "kokoro"
            || (state.characterDraft.ttsProvider == "inherit" && state.voiceProvider == .kokoro)
    }

    private var usesMacVoice: Bool {
        state.characterDraft.ttsProvider == "macos"
            || (state.characterDraft.ttsProvider == "inherit" && state.voiceProvider == .macos)
    }
}
