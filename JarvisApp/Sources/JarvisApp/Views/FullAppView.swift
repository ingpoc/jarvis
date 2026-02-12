import SwiftUI

private struct ChatMessage: Identifiable {
    let id = UUID()
    let role: String
    let text: String
}

private struct ChatResultPayload: Decodable {
    let status: String?
    let reply: String?
    let error: String?
}

private struct ChatCommandResponse: Decodable {
    let data: ChatResultPayload?
    let reply: String?
    let error: String?
}

struct FullAppView: View {
    @Environment(\.webSocket) private var webSocket
    @State private var inputText = ""
    @State private var messages: [ChatMessage] = []
    @FocusState private var inputFocused: Bool
    @State private var isSending = false
    @State private var activeSendToken: UUID?

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
                        ZStack(alignment: .topLeading) {
                            TextEditor(text: $inputText)
                                .font(.body)
                                .focused($inputFocused)
                                .frame(minHeight: 44, maxHeight: 120)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 4)
                                .background(Color(nsColor: .textBackgroundColor))
                                .overlay(
                                    RoundedRectangle(cornerRadius: 8)
                                        .stroke(Color.secondary.opacity(0.25), lineWidth: 1)
                                )
                                .cornerRadius(8)

                            if inputText.isEmpty {
                                Text("Ask Jarvis anything...")
                                    .foregroundStyle(.secondary)
                                    .padding(.horizontal, 12)
                                    .padding(.vertical, 10)
                                    .allowsHitTesting(false)
                            }
                        }
                        .onTapGesture {
                            inputFocused = true
                        }

                        Button("Send") {
                            sendMessage()
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(isSending || inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
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
            NSApp.setActivationPolicy(.regular)
            NSApp.activate(ignoringOtherApps: true)
            (NSApp.windows.first { $0.title == "Jarvis" } ?? NSApp.keyWindow)?.makeKeyAndOrderFront(nil)
            webSocket.connect()
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                inputFocused = true
            }
        }
    }

    private func sendMessage() {
        let text = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        guard !isSending else { return }
        let sendToken = UUID()
        activeSendToken = sendToken
        isSending = true
        inputText = ""
        messages.append(ChatMessage(role: "user", text: text))

        // Safety net: never leave Send button disabled if backend response stalls.
        DispatchQueue.main.asyncAfter(deadline: .now() + 35) {
            if activeSendToken == sendToken {
                isSending = false
                activeSendToken = nil
            }
        }

        Task {
            defer {
                Task { @MainActor in
                    if activeSendToken == sendToken {
                        isSending = false
                        activeSendToken = nil
                    }
                }
            }
            do {
                let resp: ChatCommandResponse = try await webSocket.send(
                    action: "chat",
                    data: ["message": text],
                    timeout: 75
                )
                let reply = resp.data?.reply ?? resp.reply
                let err = resp.data?.error ?? resp.error
                await MainActor.run {
                    if let reply, !reply.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        messages.append(ChatMessage(role: "jarvis", text: reply))
                    } else if let err, !err.isEmpty {
                        messages.append(ChatMessage(role: "jarvis", text: "Error: \(err)"))
                    } else {
                        messages.append(ChatMessage(role: "jarvis", text: "No response text returned."))
                    }
                }
            } catch {
                await MainActor.run {
                    messages.append(ChatMessage(role: "jarvis", text: "Error: \(error.localizedDescription)"))
                }
            }
        }
    }
}
