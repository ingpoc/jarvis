import SwiftUI

struct ApprovalView: View {
    @Environment(WebSocketClient.self) private var ws

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(ws.pendingApprovals) { event in
                VStack(alignment: .leading, spacing: 6) {
                    Text(event.summary)
                        .font(.callout)

                    HStack(spacing: 10) {
                        Button("Approve") {
                            approve(event)
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(.green)
                        .controlSize(.small)

                        Button("Deny") {
                            deny(event)
                        }
                        .buttonStyle(.bordered)
                        .tint(.red)
                        .controlSize(.small)
                    }
                }
                .padding(8)
                .background(.orange.opacity(0.1))
                .cornerRadius(8)
            }
        }
    }

    private func approve(_ event: TimelineEvent) {
        let taskId = event.taskId ?? "\(event.id ?? 0)"
        ws.sendCommand(action: "approve", data: ["task_id": taskId])
        ws.pendingApprovals.removeAll { $0.id == event.id }
    }

    private func deny(_ event: TimelineEvent) {
        let taskId = event.taskId ?? "\(event.id ?? 0)"
        ws.sendCommand(action: "deny", data: ["task_id": taskId])
        ws.pendingApprovals.removeAll { $0.id == event.id }
    }
}
