import SwiftUI

struct ProjectsView: View {
    var body: some View {
        ContentUnavailableView {
            Label("Projects", systemImage: "square.stack.3d.up")
        } description: {
            Text("Project history and resumable job manifests will appear here in the next implementation phase.")
        }
        .navigationTitle("Projects")
    }
}
