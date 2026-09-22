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
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("New Project") {
                    state.newProject()
                }
                .keyboardShortcut("n", modifiers: .command)
            }

            CommandMenu("AnimeDubber") {
                Button("System Check") {
                    state.runSystemCheck()
                }
                .keyboardShortcut("d", modifiers: [.command, .shift])

                if state.activeJobID != nil {
                    Divider()
                    Button("Pause Current Job") {
                        state.cancelActiveJob()
                    }
                    .keyboardShortcut(".", modifiers: .command)
                }
            }
        }

        Settings {
            SettingsView()
                .environmentObject(state)
                .frame(width: 720, height: 620)
        }
    }
}
