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

                            Image(systemName: iconForType(event.eventType))
                                .font(.caption2)
                                .foregroundStyle(EventColors.color(for: event.eventType))
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

    private func iconForType(_ type: String) -> String {
        switch type {
        case "tool_use": return "wrench.and.screwdriver"
        case "approval_needed": return "hand.raised.fill"
        case "error", "failure": return "xmark.circle.fill"
        case "success", "complete": return "checkmark.circle.fill"
        case "build_start": return "hammer.fill"
        case "build_end": return "hammer"
        case "test_start": return "flask.fill"
        case "test_end": return "flask"
        case "task_start": return "play.circle.fill"
        case "task_complete": return "checkmark.seal.fill"
        default: return "circle.fill"
        }
    }
}
