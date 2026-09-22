import Foundation

struct AppPreferences: Codable, Equatable {
    var outputFolder = "~/Movies/AnimeDubber"
    var seriesID = "10000-years-cultivation"
    var outputMode = OutputMode.dub.rawValue
    var asrProvider = ASRProvider.auto.rawValue
    var fasterWhisperModel = "large-v3"
    var fasterWhisperDevice = "auto"
    var fasterWhisperComputeType = "auto"
    var translationProvider = TranslationProvider.llm.rawValue
    var ollamaURL = "http://127.0.0.1:11434"
    var ollamaModel = "qwen3:4b"
    var voiceProvider = VoiceProvider.macos.rawValue
    var fallbackVoice = ""
    var ttsRate = 210
    var piperModel = ""
    var piperSpeaker = -1
    var elevenLabsVoiceID = "JBFqnCBsd6RMkjVDRZzb"
    var detectCharacters = true
    var resumeCachedWork = true
    var speakerBackend = "auto"
    var maxSpeakers = 12
    var speakerThreshold = 0.0
    var seriesContext = "Chinese xianxia/xuanhuan cultivation animation. Keep names, sects, realms, system terms, and cultivation terminology consistent."
    var backgroundVolume = 1.0
    var dubVolume = 1.15
    var backgroundDucking = false

    static let defaultsKey = "AnimeDubberPreferences.v1"

    static func load() -> AppPreferences {
        guard let data = UserDefaults.standard.data(forKey: defaultsKey),
              let decoded = try? JSONDecoder().decode(AppPreferences.self, from: data) else {
            return AppPreferences()
        }
        return decoded
    }

    func save() {
        guard let data = try? JSONEncoder().encode(self) else { return }
        UserDefaults.standard.set(data, forKey: Self.defaultsKey)
    }
}
