import SwiftUI

struct CommandInputView: View {
    @Environment(WebSocketClient.self) private var ws
    @State private var command = ""
    @State private var isSubmitting = false
    @FocusState private var isFocused: Bool

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "chevron.right")
                .font(.system(.body, design: .monospaced))
                .foregroundStyle(.secondary)

            TextField("Delegate a task...", text: $command)
                .textFieldStyle(.plain)
                .font(.system(.body, design: .monospaced))
                .focused($isFocused)
                .onSubmit {
                    submitCommand()
                }
                .disabled(!ws.isConnected || isSubmitting)

            if isSubmitting {
                ProgressView()
                    .controlSize(.small)
            } else {
                Button(action: submitCommand) {
                    Image(systemName: "arrow.up.circle.fill")
                        .foregroundStyle(command.isEmpty ? .gray : .blue)
                }
                .buttonStyle(.plain)
                .disabled(command.isEmpty || !ws.isConnected)
            }
        }
        .padding(10)
        .background(.quaternary.opacity(0.5))
        .cornerRadius(8)
    }

    private func submitCommand() {
        let trimmed = command.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, ws.isConnected else { return }

        isSubmitting = true
        ws.runTask(description: trimmed)
        command = ""

        // Reset submitting state after a brief delay
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            isSubmitting = false
        }
    }
}
