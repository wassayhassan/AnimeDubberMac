import SwiftUI

struct CharactersView: View {
    var body: some View {
        ContentUnavailableView {
            Label("Characters", systemImage: "person.2")
        } description: {
            Text("Character tables, voice previews, and the native inspector are the next SwiftUI feature to be connected.")
        }
        .navigationTitle("Characters")
    }
}
