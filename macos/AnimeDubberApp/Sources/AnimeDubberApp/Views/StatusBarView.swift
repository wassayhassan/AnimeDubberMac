import SwiftUI

struct StatusBarView: View {
    @EnvironmentObject private var state: AppState

    var body: some View {
        VStack(spacing: 0) {
            if state.activityExpanded {
                ActivityDrawer()
                    .frame(height: 230)
                Divider()
            }

            HStack(spacing: 12) {
                Circle()
                    .fill(state.activeJobID == nil ? Color.secondary : Color.accentColor)
                    .frame(width: 7, height: 7)

                Text(state.statusText)
                    .font(.callout)
                    .lineLimit(1)

                if let progress = state.progressFraction {
                    ProgressView(value: progress)
                        .frame(width: 120)
                    Text(progress, format: .percent.precision(.fractionLength(0)))
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary)
                }

                Spacer()

                if state.activeJobID != nil {
                    Button("Pause") {
                        state.cancelActiveJob()
                    }
                    .foregroundStyle(.red)
                }

                Button {
                    withAnimation(.snappy) {
                        state.activityExpanded.toggle()
                    }
                } label: {
                    Label(
                        "Activity",
                        systemImage: state.activityExpanded ? "chevron.down" : "chevron.up"
                    )
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 14)
            .frame(height: 38)
            .background(.bar)
        }
        .overlay(alignment: .top) {
            Divider()
        }
    }
}
