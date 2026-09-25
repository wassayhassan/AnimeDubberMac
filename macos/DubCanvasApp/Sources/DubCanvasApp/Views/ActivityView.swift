import SwiftUI

struct ActivityView: View {
    @EnvironmentObject private var state: AppState

    var body: some View {
        VStack(spacing: 0) {
            if state.activity.isEmpty {
                ContentUnavailableView(
                    "No Activity Yet",
                    systemImage: "list.bullet.rectangle",
                    description: Text("Start an analysis or dub to see structured job activity.")
                )
            } else {
                List(state.activity) { entry in
                    HStack(alignment: .top, spacing: 10) {
                        Image(systemName: entry.symbol)
                            .foregroundStyle(entry.tint)
                        Text(entry.message)
                            .textSelection(.enabled)
                    }
                    .padding(.vertical, 2)
                }
            }
        }
        .navigationTitle("Activity")
    }
}
