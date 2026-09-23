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

    var voiceProvider = VoiceProvider.auto.rawValue
    var fallbackVoice = ""
    var ttsRate = 210
    var chatterboxReferenceAudio = ""
    var autoSourceVoices: Bool? = true
    var chatterboxExpressiveness = 0.5
    var chatterboxDevice = "auto"
    var chatterboxTurbo = true
    var kokoroVoice = "auto"
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

    static let defaultsKey = "AnimeDubberPreferences.v2"

    static func load() -> AppPreferences {
        if let data = UserDefaults.standard.data(forKey: defaultsKey),
           let decoded = try? JSONDecoder().decode(AppPreferences.self, from: data) {
            return decoded
        }

        // Migrate the older v1 preferences without failing when new voice fields
        // did not exist yet. New voice defaults use Automatic / Best Local.
        if let oldData = UserDefaults.standard.data(forKey: "AnimeDubberPreferences.v1"),
           let object = try? JSONSerialization.jsonObject(with: oldData) as? [String: Any] {
            var migrated = AppPreferences()
            migrated.outputFolder = object["outputFolder"] as? String ?? migrated.outputFolder
            migrated.seriesID = object["seriesID"] as? String ?? migrated.seriesID
            migrated.outputMode = object["outputMode"] as? String ?? migrated.outputMode
            migrated.asrProvider = object["asrProvider"] as? String ?? migrated.asrProvider
            migrated.translationProvider = object["translationProvider"] as? String ?? migrated.translationProvider
            migrated.voiceProvider = VoiceProvider.auto.rawValue
            migrated.fallbackVoice = object["fallbackVoice"] as? String ?? ""
            migrated.ttsRate = object["ttsRate"] as? Int ?? migrated.ttsRate
            migrated.detectCharacters = object["detectCharacters"] as? Bool ?? migrated.detectCharacters
            migrated.resumeCachedWork = object["resumeCachedWork"] as? Bool ?? migrated.resumeCachedWork
            migrated.backgroundDucking = object["backgroundDucking"] as? Bool ?? migrated.backgroundDucking
            migrated.save()
            return migrated
        }

        return AppPreferences()
    }

    func save() {
        guard let data = try? JSONEncoder().encode(self) else { return }
        UserDefaults.standard.set(data, forKey: Self.defaultsKey)
    }
}


struct SettingsSnapshot: Equatable {
    let outputFolder: String
    let seriesID: String
    let outputMode: OutputMode
    let asrProvider: ASRProvider
    let fasterWhisperModel: String
    let fasterWhisperDevice: String
    let fasterWhisperComputeType: String
    let translationProvider: TranslationProvider
    let ollamaURL: String
    let ollamaModel: String
    let voiceProvider: VoiceProvider
    let fallbackVoice: String
    let ttsRate: Int
    let chatterboxReferenceAudio: String
    let autoSourceVoices: Bool
    let chatterboxExpressiveness: Double
    let chatterboxDevice: String
    let chatterboxTurbo: Bool
    let kokoroVoice: String
    let piperModel: String
    let piperSpeaker: Int
    let elevenLabsVoiceID: String
    let detectCharacters: Bool
    let resumeCachedWork: Bool
    let speakerBackend: String
    let maxSpeakers: Int
    let speakerThreshold: Double
    let seriesContext: String
    let backgroundVolume: Double
    let dubVolume: Double
    let backgroundDucking: Bool
}
