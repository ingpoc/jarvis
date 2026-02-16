import SwiftUI

struct ApprovalView: View {
    @Environment(WebSocketClient.self) private var ws

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(ws.pendingApprovals) { event in
                ApprovalCard(event: event, ws: ws)
            }
        }
    }
}

// MARK: - Approval Card with Modify-Input

struct ApprovalCard: View {
    let event: TimelineEvent
    let ws: WebSocketClient
    @State private var isEditing = false
    @State private var modifiedInput = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(event.summary)
                .font(.callout)

            // Modify-input text field
            if isEditing {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Modify request:")
                        .font(.caption)
                        .foregroundStyle(.secondary)

                    TextField("Enter modified instructions...", text: $modifiedInput, axis: .vertical)
                        .textFieldStyle(.roundedBorder)
                        .font(.caption)
                        .lineLimit(2...4)
                }
                .transition(.opacity.combined(with: .move(edge: .top)))
            }

            HStack(spacing: 8) {
                Button("Approve") {
                    approve()
                }
                .buttonStyle(.borderedProminent)
                .tint(.green)
                .controlSize(.small)

                Button("Deny") {
                    deny()
                }
                .buttonStyle(.bordered)
                .tint(.red)
                .controlSize(.small)

                Spacer()

                Button(isEditing ? "Cancel" : "Modify") {
                    withAnimation(.easeInOut(duration: 0.15)) {
                        if isEditing {
                            modifiedInput = ""
                        }
                        isEditing.toggle()
                    }
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
            }
        }
        .padding(8)
        .background(.orange.opacity(0.1))
        .cornerRadius(8)
    }

    private func approve() {
        let taskId = event.taskId ?? "\(event.id ?? 0)"
        if isEditing && !modifiedInput.isEmpty {
            ws.sendCommand(action: "approve", data: [
                "task_id": taskId,
                "modified_input": modifiedInput,
            ])
        } else {
            ws.sendCommand(action: "approve", data: ["task_id": taskId])
        }
        ws.pendingApprovals.removeAll { $0.id == event.id }
    }

    private func deny() {
        let taskId = event.taskId ?? "\(event.id ?? 0)"
        ws.sendCommand(action: "deny", data: ["task_id": taskId])
        ws.pendingApprovals.removeAll { $0.id == event.id }
    }
}
