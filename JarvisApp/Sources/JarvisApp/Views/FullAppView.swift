import SwiftUI

private struct ChatMessage: Identifiable {
    let id = UUID()
    let role: String
    let text: String
}

private enum FullAppSection: String, CaseIterable, Identifiable {
    case chat = "Chat"
    case timeline = "Timeline"
    case commandCenter = "Command Center"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .chat: "bubble.left.and.bubble.right.fill"
        case .timeline: "clock.arrow.circlepath"
        case .commandCenter: "chart.bar.doc.horizontal"
        }
    }
}

private struct ChatResultPayload: Decodable {
    let status: String?
    let reply: String?
    let error: String?
    let route: String?
    let suggestion: String?
    let queued: String?
    let nextAction: String?

    private enum CodingKeys: String, CodingKey {
        case status
        case reply
        case error
        case route
        case suggestion
        case queued
        case nextAction = "next_action"
    }
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
    @State private var selectedSection: FullAppSection = .chat

    private var recentEvents: [TimelineEvent] {
        Array(
            webSocket.events
                .sorted { $0.timestamp > $1.timestamp }
                .prefix(80)
        )
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 12) {
                StatusBadge()

                Divider()
                    .frame(height: 26)

                Picker("Section", selection: $selectedSection) {
                    ForEach(FullAppSection.allCases) { section in
                        Label(section.rawValue, systemImage: section.icon)
                            .tag(section)
                    }
                }
                .pickerStyle(.segmented)
                .frame(maxWidth: 520)

                Spacer()

                if webSocket.connectionState == .connected {
                    Label("Connected", systemImage: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                } else {
                    Label("Disconnected", systemImage: "xmark.circle.fill")
                        .foregroundStyle(.red)
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)

            Divider()

            HStack(spacing: 0) {
                Group {
                    switch selectedSection {
                    case .chat:
                        chatPanel
                    case .timeline:
                        timelinePanel
                    case .commandCenter:
                        commandCenterPanel
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)

                Divider()

                activityPanel
                    .frame(width: 380)
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

    private var chatPanel: some View {
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
                        .cornerRadius(10)
                    }
                }
                .padding(16)
            }

            Divider()

            HStack(spacing: 10) {
                ZStack(alignment: .topLeading) {
                    TextEditor(text: $inputText)
                        .font(.body)
                        .focused($inputFocused)
                        .frame(minHeight: 44, maxHeight: 140)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 6)
                        .background(Color(nsColor: .textBackgroundColor))
                        .overlay(
                            RoundedRectangle(cornerRadius: 10)
                                .stroke(Color.secondary.opacity(0.25), lineWidth: 1)
                        )
                        .cornerRadius(10)

                    if inputText.isEmpty {
                        Text("Ask Jarvis anything...")
                            .foregroundStyle(.secondary)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 12)
                            .allowsHitTesting(false)
                    }
                }
                .onTapGesture { inputFocused = true }

                Button {
                    sendMessage()
                } label: {
                    Label("Send", systemImage: "paperplane.fill")
                }
                .buttonStyle(.borderedProminent)
                .disabled(isSending || inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                .controlSize(.large)
            }
            .padding(16)
        }
    }

    private var timelinePanel: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Timeline")
                .font(.headline)
                .padding(.horizontal, 16)
                .padding(.top, 14)
                .padding(.bottom, 6)

            TimelineView()
                .padding(.bottom, 12)
        }
    }

    private var commandCenterPanel: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Command Center")
                .font(.headline)
                .padding(.horizontal, 16)
                .padding(.top, 14)
                .padding(.bottom, 6)

            CommandCenterView()
                .padding(.bottom, 12)
        }
    }

    private var activityPanel: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("Live Events")
                    .font(.headline)

                Spacer()

                Button("Refresh") {
                    Task {
                        try? await webSocket.sendWithoutResponse(action: "get_status", data: nil)
                        try? await webSocket.sendWithoutResponse(action: "get_available_tools", data: nil)
                        try? await webSocket.sendWithoutResponse(action: "get_containers", data: nil)
                    }
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
            }
            .padding(.horizontal, 16)
            .padding(.top, 14)
            .padding(.bottom, 10)

            Divider()

            ScrollView {
                LazyVStack(alignment: .leading, spacing: 8) {
                    ForEach(recentEvents) { event in
                        HStack(alignment: .top, spacing: 10) {
                            Text(event.timeString)
                                .font(.system(.caption, design: .monospaced))
                                .foregroundStyle(.secondary)
                                .frame(width: 64, alignment: .leading)

                            Image(systemName: iconForType(event.eventType))
                                .font(.caption2)
                                .foregroundStyle(EventColors.color(for: event.eventType))
                                .frame(width: 18)

                            VStack(alignment: .leading, spacing: 2) {
                                Text(event.eventType)
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                                Text(event.summary)
                                    .font(.caption)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 2)
                    }
                }
                .padding(.vertical, 10)
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
                    action: "message",
                    data: ["message": text],
                    timeout: 75
                )
                let payload = resp.data
                let reply = payload?.reply ?? resp.reply
                let err = payload?.error ?? resp.error
                await MainActor.run {
                    if let reply, !reply.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        messages.append(ChatMessage(role: "jarvis", text: reply))
                    } else if payload?.status == "requires_confirmation",
                              let suggestion = payload?.suggestion, !suggestion.isEmpty {
                        messages.append(ChatMessage(role: "jarvis", text: suggestion))
                    } else if payload?.status == "queued",
                              let queued = payload?.queued, !queued.isEmpty {
                        messages.append(ChatMessage(role: "jarvis", text: "Queued task: \(queued)"))
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
