import SwiftUI

struct TimelineView: View {
    @Environment(WebSocketClient.self) private var ws

    var body: some View {
        let visible = Array(ws.events.prefix(50))

        if visible.isEmpty {
            Text("No events yet")
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, minHeight: 60)
        } else {
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 6) {
                    ForEach(visible) { event in
                        HStack(alignment: .top, spacing: 8) {
                            Text(event.timeString)
                                .font(.system(.caption, design: .monospaced))
                                .foregroundStyle(.secondary)
                                .frame(width: 64, alignment: .leading)

                            Text(event.eventType)
                                .font(.caption)
                                .fontWeight(.semibold)
                                .foregroundStyle(colorForType(event.eventType))
                                .frame(width: 80, alignment: .leading)

                            Text(event.summary)
                                .font(.caption)
                                .lineLimit(2)
                        }
                        .padding(.horizontal, 16)
                    }
                }
                .padding(.vertical, 6)
            }
        }
    }

    private func colorForType(_ type: String) -> Color {
        switch type {
        case "approval_needed": .orange
        case "error", "failure": .red
        case "success", "complete": .green
        case "build_start", "build_end": .blue
        case "test_start", "test_end": .yellow
        default: .primary
        }
    }
}
