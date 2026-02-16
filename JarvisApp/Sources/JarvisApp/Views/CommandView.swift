import SwiftUI

/// Command View: Execute tasks and manage approvals
/// Design: Clear input, prominent actions, minimal friction
struct CommandView: View {
    @State private var commandInput = ""
    @State private var isExecuting = false
    @FocusState private var isInputFocused: Bool

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // Command Input
                CommandInputCard(
                    input: $commandInput,
                    isFocused: $isInputFocused,
                    isExecuting: $isExecuting
                )

                // Pending Approvals
                if !pendingApprovals.isEmpty {
                    ApprovalsSection()
                }

                // Command History
                CommandHistorySection()

                Spacer()
            }
            .padding(24)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(nsColor: .textBackgroundColor))
    }

    private var pendingApprovals: [TimelineEvent] {
        // TODO: Get from WebSocket client
        []
    }
}

// MARK: - Command Input Card

struct CommandInputCard: View {
    @Binding var input: String
    @FocusState.Binding var isFocused: Bool
    @Binding var isExecuting: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Execute Command")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(.secondary)

            HStack(spacing: 12) {
                TextField("Describe what Jarvis should do...", text: $input)
                    .textFieldStyle(.plain)
                    .font(.system(size: 13))
                    .focused($isFocused)
                    .disabled(isExecuting)
                    .onSubmit {
                        executeCommand()
                    }

                if isExecuting {
                    ProgressView()
                        .controlSize(.small)
                } else if !input.isEmpty {
                    Button(action: executeCommand) {
                        Image(systemName: "arrow.up.circle.fill")
                            .font(.system(size: 20))
                            .foregroundStyle(.accentColor)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .background(Color(nsColor: .controlBackgroundColor))
            .cornerRadius(8)
        }
    }

    private func executeCommand() {
        guard !input.isEmpty else { return }
        isExecuting = true
        // TODO: Send command via WebSocket
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            isExecuting = false
            input = ""
        }
    }
}

// MARK: - Approvals Section

struct ApprovalsSection: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Pending Approvals")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(.secondary)

            VStack(spacing: 8) {
                ApprovalCard(
                    task: "Install new dependencies",
                    reason: "Package management",
                    onApprove: { },
                    onDeny: { }
                )

                ApprovalCard(
                    task: "Modify configuration files",
                    reason: "System settings",
                    onApprove: { },
                    onDeny: { }
                )
            }
        }
    }
}

struct ApprovalCard: View {
    let task: String
    let reason: String
    let onApprove: () -> Void
    let onDeny: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text(task)
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(.primary)

                Text(reason)
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
            }

            Spacer()

            HStack(spacing: 8) {
                Button("Deny", action: onDeny)
                    .buttonStyle(.approvalStyle(color: .red))

                Button("Approve", action: onApprove)
                    .buttonStyle(.approvalStyle(color: .green))
            }
        }
        .padding(16)
        .background(Color(nsColor: .controlBackgroundColor))
        .cornerRadius(8)
    }
}

struct ApprovalStyle: ButtonStyle {
    let color: Color

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 11, weight: .semibold))
            .foregroundStyle(configuration.isPressed ? color.opacity(0.7) : color)
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(color.opacity(0.1))
            .cornerRadius(4)
    }
}

extension ButtonStyle where Self == ApprovalStyle {
    static func approvalStyle(color: Color) -> ApprovalStyle {
        ApprovalStyle(color: color)
    }
}

// MARK: - Command History Section

struct CommandHistorySection: View {
    private let history = [
        ("Run test suite", "Completed", "2m ago"),
        ("Build project", "Completed", "5m ago"),
        ("Git status", "Completed", "8m ago"),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Recent Commands")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(.secondary)

            VStack(spacing: 0) {
                ForEach(Array(history.enumerated()), id: \.offset) { index, item in
                    HistoryRow(command: item.0, status: item.1, time: item.2)
                    if index < history.count - 1 {
                        Divider().padding(.leading, 44)
                    }
                }
            }
            .background(Color(nsColor: .controlBackgroundColor))
            .cornerRadius(8)
        }
    }
}

struct HistoryRow: View {
    let command: String
    let status: String
    let time: String

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: status == "Completed" ? "checkmark.circle.fill" : "circle")
                .font(.system(size: 12))
                .foregroundStyle(status == "Completed" ? .green : .secondary)
                .frame(width: 20)

            Text(command)
                .font(.system(size: 12))
                .foregroundStyle(.primary)

            Spacer()

            Text(time)
                .font(.system(size: 10))
                .foregroundStyle(.tertiary)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
    }
}
