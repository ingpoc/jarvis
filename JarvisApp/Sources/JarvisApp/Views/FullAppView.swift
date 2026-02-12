import SwiftUI

private struct ChatMessage: Identifiable {
    let id = UUID()
    let role: String
    let text: String
}

struct FullAppView: View {
    @Environment(\.webSocket) private var webSocket
    @State private var inputText = ""
    @State private var messages: [ChatMessage] = []

    private var recentEvents: [TimelineEvent] {
        Array(webSocket.events.suffix(80).reversed())
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("Jarvis Chat")
                    .font(.title2)
                    .fontWeight(.semibold)
                Spacer()
                if webSocket.connectionState == .connected {
                    Label("Connected", systemImage: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                } else {
                    Label("Disconnected", systemImage: "xmark.circle.fill")
                        .foregroundStyle(.red)
                }
            }
            .padding(16)

            Divider()

            HStack(spacing: 0) {
                VStack(spacing: 0) {
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 10) {
                            ForEach(messages) { msg in
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(msg.role.uppercased())
                                        .font(.caption2)
                                        .foregroundStyle(.secondary)
                                    Text(msg.text)
                                        .font(.body)
                                }
                                .padding(10)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .background(msg.role == "user" ? Color.blue.opacity(0.12) : Color.secondary.opacity(0.12))
                                .cornerRadius(8)
                            }
                        }
                        .padding(12)
                    }

                    Divider()

                    HStack(spacing: 8) {
                        TextField("Ask Jarvis anything...", text: $inputText, axis: .vertical)
                            .textFieldStyle(.roundedBorder)
                            .lineLimit(1...6)

                        Button("Send") {
                            sendMessage()
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    }
                    .padding(12)
                }

                Divider()

                VStack(alignment: .leading, spacing: 8) {
                    Text("Live Events")
                        .font(.headline)
                        .padding(.top, 12)
                        .padding(.horizontal, 12)

                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 8) {
                            ForEach(recentEvents) { event in
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(event.eventType)
                                        .font(.caption2)
                                        .foregroundStyle(.secondary)
                                    Text(event.summary)
                                        .font(.caption)
                                }
                                .padding(.horizontal, 12)
                            }
                        }
                        .padding(.vertical, 8)
                    }
                }
                .frame(width: 360)
            }
        }
        .onAppear {
            webSocket.connect()
        }
    }

    private func sendMessage() {
        let text = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        inputText = ""
        messages.append(ChatMessage(role: "user", text: text))
        messages.append(ChatMessage(role: "jarvis", text: "Queued: \(text)"))

        Task {
            try? await webSocket.sendWithoutResponse(action: "run_task", data: ["description": text])
        }
    }
}

