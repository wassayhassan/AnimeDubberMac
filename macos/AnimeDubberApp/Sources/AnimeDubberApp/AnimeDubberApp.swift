import SwiftUI

@main
struct AnimeDubberApp: App {
    @StateObject private var state = AppState()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(state)
                .frame(minWidth: 940, minHeight: 650)
        }
        .defaultSize(width: 1180, height: 780)

        Settings {
            SettingsView()
                .environmentObject(state)
                .frame(width: 560, height: 430)
        }
    }
}
