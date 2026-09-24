import SwiftUI

struct ProcessingView: View {
    @EnvironmentObject private var state: AppState

    private let steps: [(String, String)] = [
        ("downloading", "Preparing video"),
        ("extracting_audio", "Extracting audio"),
        ("separating_stems", "Separating dialogue"),
        ("transcribing", "Understanding speech"),
        ("translating", "Translating subtitles"),
        ("analyzing_characters", "Matching characters"),
        ("synthesizing", "Generating voices"),
        ("mixing", "Aligning and mixing audio"),
        ("exporting", "Finishing video"),
    ]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text(state.outputMode == .subtitles ? "Your subtitles" : "Your dub")
                    .font(.largeTitle.bold())
                Text(state.source.isEmpty ? "Preparing your video" :
                     (URL(string: state.source)?.scheme == "https" || URL(string: state.source)?.scheme == "http" ?
                      state.source : URL(fileURLWithPath: state.source).lastPathComponent))
                    .font(.title3).lineLimit(2)

                if !state.jobIssue.isEmpty {
                    GroupBox("Needs attention") {
                        VStack(alignment: .leading, spacing: 12) {
                            Label(state.jobIssue, systemImage: "exclamationmark.triangle.fill")
                                .foregroundStyle(.orange)
                            HStack {
                                Button("Try Again") {
                                    state.selection = .newProject
                                }.buttonStyle(.borderedProminent)
                                Button("System Check") { state.runSystemCheck() }
                                Button("Technical Details") { state.activityExpanded = true }
                            }
                        }.frame(maxWidth: .infinity, alignment: .leading)
                    }
                } else {
                    GroupBox("Progress") {
                        VStack(alignment: .leading, spacing: 16) {
                            Text(state.startPending ? "Checking your setup and creating a project…" :
                                 state.activeJobID == nil ? state.statusText :
                                 steps.first(where: { $0.0 == state.currentStage })?.1 ?? "Processing video")
                                .font(.headline)
                            if state.activeJobID != nil {
                                if let fraction = state.progressFraction {
                                    ProgressView(value: fraction)
                                    Text("Current step: \(fraction, format: .percent.precision(.fractionLength(0)))")
                                        .font(.caption).foregroundStyle(.secondary)
                                } else {
                                    ProgressView()
                                }
                            } else if state.startPending || state.jobStartPending {
                                ProgressView()
                            }
                            if !state.downloadDetail.isEmpty && state.currentStage == "downloading" {
                                Text(state.downloadDetail).font(.callout)
                            }
                            if !state.stageDetail.isEmpty {
                                Text(state.stageDetail).font(.caption).foregroundStyle(.secondary)
                            }
                            Text("The percentage describes the current step; the whole job may take longer. The first run may also download voice and language models.")
                                .font(.caption).foregroundStyle(.secondary)
                            if state.activeJobID != nil {
                                Button("Pause and keep completed work") { state.cancelActiveJob() }
                            }
                        }.frame(maxWidth: .infinity, alignment: .leading)
                    }
                }

                DisclosureGroup("Technical activity") {
                    ActivityDrawer().frame(height: 240)
                }
            }
            .frame(maxWidth: 720, alignment: .leading)
            .padding(28)
            .frame(maxWidth: .infinity, alignment: .topLeading)
        }
        .navigationTitle("Processing")
    }
}
