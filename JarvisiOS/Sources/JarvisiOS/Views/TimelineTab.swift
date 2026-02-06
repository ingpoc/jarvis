import SwiftUI
import JarvisClient

struct TimelineTab: View {
    @State private var client = JarvisWebSocketClient.shared

    var body: some View {
        NavigationStack {
            List {
                ForEach(client.events) { event in
                    EventDetailRow(event: event)
                        .contentShape(Rectangle())
                        .onTapGesture {
                        }
                }
            }
            .optionalListStyle()
            .refreshable {
                await refreshTimeline()
            }
            .navigationTitle("Timeline")
        }
        .onAppear { client.connect() }
        .onDisappear { client.disconnect() }
    }

    private func refreshTimeline() async {
    }
}

struct EventDetailRow: View {
    let event: TimelineEvent

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: iconName)
                .font(.system(size: 14))
                .foregroundStyle(iconColor)
                .frame(width: 24)

            VStack(alignment: .leading, spacing: 4) {
                Text(event.summary)
                    .font(.system(size: 14))

                HStack(spacing: 8) {
                    Text(event.timeString)
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)

                    if let cost = event.costUsd, cost > 0 {
                        Text("+")
                            .foregroundStyle(.secondary)

                        Text("$\(String(format: "%.2f", cost))")
                            .font(.system(size: 11))
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
        .padding(.vertical, 4)
    }

    private var iconName: String {
        switch event.eventType {
        case "error": return "xmark.circle.fill"
        case "approval_needed": return "hand.raised.fill"
        case "task_start": return "play.circle.fill"
        case "task_complete": return "checkmark.circle.fill"
        case "feature_start": return "sparkles"
        case "tool_use": return "wrench.and.screwdriver"
        default: return "circle.fill"
        }
    }

    private var iconColor: Color {
        switch event.eventType {
        case "error": return .red
        case "approval_needed": return .orange
        case "task_start": return .blue
        case "task_complete": return .green
        case "feature_complete": return .green
        default: return .secondary
        }
    }
}
