import SwiftUI
import AppKit

private struct ChatModelOption: Identifiable, Hashable {
    let id: String
    let name: String
    let provider: String
    let icon: String
}

private enum ChatProviderKey: String, CaseIterable {
    case anthropic
    case foundation
    case opencode

    var label: String {
        switch self {
        case .anthropic: return "Anthropic"
        case .foundation: return "Foundation"
        case .opencode: return "OpenCode"
        }
    }
}

private struct ChatWorkspaceMessage: Identifiable {
    let id = UUID()
    let role: String
    let text: String
}

private struct ChatWorkspacePayload: Decodable {
    let status: String?
    let reply: String?
    let error: String?
    let suggestion: String?
    let queued: Bool?
}

private struct ChatWorkspaceResponse: Decodable {
    let data: ChatWorkspacePayload?
    let reply: String?
    let error: String?
}

struct ChatWorkspaceView: View {
    @Environment(\.webSocket) private var webSocket
    @State private var inputText = ""
    @State private var messages: [ChatWorkspaceMessage] = []
    @State private var isSending = false
    @State private var activeSendToken: UUID?
    @State private var selectedModelId = "claude-sonnet-4-5-20250929"
    @State private var selectedProvider: ChatProviderKey = .anthropic
    @State private var inputFocused = false
    @State private var seenEventIds: Set<String> = []

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 10) {
                Text("Chat")
                    .font(.headline)

                Spacer()

                Picker("Provider", selection: Binding(
                    get: { selectedProvider },
                    set: { newValue in
                        guard newValue != selectedProvider else { return }
                        selectedProvider = newValue
                        selectDefaultModelForProvider(newValue)
                    }
                )) {
                    ForEach(providerOptions, id: \.self) { provider in
                        Text(provider.label).tag(provider)
                    }
                }
                .labelsHidden()
                .pickerStyle(.menu)
                .frame(minWidth: 120)

                Picker("Model", selection: Binding(
                    get: { selectedModelId },
                    set: { newValue in
                        guard newValue != selectedModelId else { return }
                        selectedModelId = newValue
                        switchModel(newValue)
                    }
                )) {
                    ForEach(modelOptionsForSelectedProvider) { option in
                        Label("\(option.name) · \(option.provider)", systemImage: option.icon)
                            .tag(option.id)
                    }
                }
                .labelsHidden()
                .pickerStyle(.menu)
                .frame(minWidth: 240)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)

            Divider()

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
                    ChatSubmitTextEditor(
                        text: $inputText,
                        isFocused: $inputFocused,
                        onSubmit: sendMessage
                    )
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
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(nsColor: .textBackgroundColor))
        .onAppear {
            webSocket.connect()
            seenEventIds = Set(webSocket.events.map(\.id))
            syncFromModelStatus(webSocket.modelStatus)
            webSocket.sendCommand(action: "get_model_status")
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                inputFocused = true
            }
        }
        .onChange(of: webSocket.modelStatus?.currentModel) { _ in
            syncFromModelStatus(webSocket.modelStatus)
        }
        .onChange(of: webSocket.modelStatus?.provider) { _ in
            syncFromModelStatus(webSocket.modelStatus)
        }
        .onChange(of: webSocket.modelStatus?.providerType) { _ in
            syncFromModelStatus(webSocket.modelStatus)
        }
        .onChange(of: webSocket.events.count) { _ in
            consumeIncomingChatEvents()
        }
    }

    private var providerOptions: [ChatProviderKey] {
        var options: [ChatProviderKey] = [.anthropic, .opencode]
        if webSocket.modelStatus?.foundationAvailable ?? true {
            options.append(.foundation)
        }
        return options
    }

    private var allModelOptions: [ChatModelOption] {
        var options: [ChatModelOption] = [
            .init(id: "claude-sonnet-4-5-20250929", name: "Claude Sonnet 4.5", provider: "Anthropic", icon: "brain"),
            .init(id: "claude-opus-4-6", name: "Claude Opus 4.6", provider: "Anthropic", icon: "brain"),
            .init(id: "claude-haiku-4-5-20251001", name: "Claude Haiku 4.5", provider: "Anthropic", icon: "brain"),
        ]

        if webSocket.modelStatus?.foundationAvailable ?? true {
            options.append(.init(id: "foundation-models", name: "Foundation Models", provider: "Apple", icon: "apple.logo"))
        }

        let fallbackOpenCodeModels = [
            "minimax-m2.5-free",
            "glm-5-free",
            "kimi-k2.5-free",
            "big-pickle",
            "openai/gpt-5-nano",
        ]
        let rawOpenCodeModels = webSocket.modelStatus?.opencodeAvailableModels ?? fallbackOpenCodeModels
        for rawModel in rawOpenCodeModels {
            let normalized = rawModel.hasPrefix("opencode/") ? rawModel : "opencode/\(rawModel)"
            options.append(
                .init(
                    id: normalized,
                    name: rawModel,
                    provider: "OpenCode",
                    icon: "shippingbox.fill"
                )
            )
        }

        // Preserve picker validity if daemon reports a model not in default options.
        if let current = webSocket.modelStatus?.currentModel,
           !current.isEmpty,
           !options.contains(where: { $0.id == current }) {
            options.append(.init(id: current, name: current, provider: "Active", icon: "checkmark.circle"))
        }

        return options
    }

    private var modelOptionsForSelectedProvider: [ChatModelOption] {
        switch selectedProvider {
        case .anthropic:
            return allModelOptions.filter { $0.provider == "Anthropic" }
        case .foundation:
            return allModelOptions.filter { $0.id == "foundation-models" }
        case .opencode:
            return allModelOptions.filter { $0.provider == "OpenCode" }
        }
    }

    private func syncFromModelStatus(_ status: ModelStatusInfo?) {
        guard let status else { return }
        guard let model = status.currentModel, !model.isEmpty else { return }
        selectedModelId = model
        selectedProvider = providerForModel(model, providerHint: status.providerType ?? status.provider)
    }

    private func providerForModel(_ modelId: String, providerHint: String?) -> ChatProviderKey {
        let hint = (providerHint ?? "").trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if hint == "opencode" {
            return .opencode
        }
        if hint == "foundation" {
            return .foundation
        }
        if modelId == "foundation-models" {
            return .foundation
        }
        if modelId.hasPrefix("opencode/") || modelId.hasPrefix("opencode:") || modelId == "opencode" {
            return .opencode
        }
        return .anthropic
    }

    private func selectDefaultModelForProvider(_ provider: ChatProviderKey) {
        let options = modelOptionsForSelectedProvider
        guard let fallback = options.first?.id else { return }
        if !options.contains(where: { $0.id == selectedModelId }) {
            selectedModelId = fallback
            switchModel(fallback)
        }
    }

    private func switchModel(_ modelId: String) {
        webSocket.sendCommand(action: "switch_model", data: ["model": modelId])
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) {
            webSocket.sendCommand(action: "get_model_status")
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            webSocket.sendCommand(action: "get_model_status")
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
        messages.append(ChatWorkspaceMessage(role: "user", text: text))

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
                let resp: ChatWorkspaceResponse = try await webSocket.send(
                    action: "message",
                    data: ["message": text],
                    timeout: 120
                )
                let payload = resp.data
                let reply = payload?.reply ?? resp.reply
                let err = payload?.error ?? resp.error
                await MainActor.run {
                    inputFocused = true
                    if let reply, !reply.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        messages.append(ChatWorkspaceMessage(role: "jarvis", text: reply))
                    } else if payload?.status == "requires_confirmation",
                              let suggestion = payload?.suggestion, !suggestion.isEmpty {
                        messages.append(ChatWorkspaceMessage(role: "jarvis", text: suggestion))
                    } else if payload?.status == "queued",
                              payload?.queued == true {
                        messages.append(ChatWorkspaceMessage(role: "jarvis", text: "Working on it. I will post the full response when finished."))
                    } else if let err, !err.isEmpty {
                        messages.append(ChatWorkspaceMessage(role: "jarvis", text: "Error: \(err)"))
                    } else {
                        messages.append(ChatWorkspaceMessage(role: "jarvis", text: "No response text returned."))
                    }
                }
            } catch {
                await MainActor.run {
                    messages.append(ChatWorkspaceMessage(role: "jarvis", text: "Error: \(error.localizedDescription)"))
                }
            }
        }
    }

    private func consumeIncomingChatEvents() {
        let pendingEvents = webSocket.events.filter { !seenEventIds.contains($0.id) }
        guard !pendingEvents.isEmpty else { return }

        for event in pendingEvents {
            seenEventIds.insert(event.id)
            switch event.eventType {
            case "chat_async_complete":
                let text = event.summary.trimmingCharacters(in: .whitespacesAndNewlines)
                if !text.isEmpty {
                    messages.append(ChatWorkspaceMessage(role: "jarvis", text: text))
                }
            case "error":
                if event.summary.lowercased().contains("background chat") {
                    messages.append(ChatWorkspaceMessage(role: "jarvis", text: "Error: \(event.summary)"))
                }
            default:
                break
            }
        }
    }
}

private struct ChatSubmitTextEditor: NSViewRepresentable {
    @Binding var text: String
    @Binding var isFocused: Bool
    let onSubmit: () -> Void

    func makeNSView(context: Context) -> NSScrollView {
        let scrollView = NSScrollView()
        scrollView.drawsBackground = false
        scrollView.borderType = .noBorder
        scrollView.hasVerticalScroller = true
        scrollView.hasHorizontalScroller = false
        scrollView.autohidesScrollers = true

        let textView = SubmitAwareTextView()
        textView.delegate = context.coordinator
        textView.font = .systemFont(ofSize: NSFont.systemFontSize)
        textView.isRichText = false
        textView.importsGraphics = false
        textView.isAutomaticQuoteSubstitutionEnabled = false
        textView.isAutomaticDashSubstitutionEnabled = false
        textView.isAutomaticTextReplacementEnabled = false
        textView.backgroundColor = .clear
        textView.string = text
        textView.textContainerInset = NSSize(width: 0, height: 4)
        textView.onSubmit = onSubmit
        textView.isVerticallyResizable = true
        textView.isHorizontallyResizable = false
        textView.textContainer?.widthTracksTextView = true
        textView.textContainer?.containerSize = NSSize(
            width: 0,
            height: CGFloat.greatestFiniteMagnitude
        )

        scrollView.documentView = textView
        context.coordinator.textView = textView
        return scrollView
    }

    func updateNSView(_ nsView: NSScrollView, context: Context) {
        guard let textView = nsView.documentView as? SubmitAwareTextView else { return }

        textView.onSubmit = onSubmit
        if textView.string != text {
            textView.string = text
        }

        guard let window = textView.window else { return }
        if isFocused, window.firstResponder !== textView {
            window.makeFirstResponder(textView)
        }
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(text: $text)
    }

    final class Coordinator: NSObject, NSTextViewDelegate {
        @Binding var text: String
        weak var textView: NSTextView?

        init(text: Binding<String>) {
            _text = text
        }

        func textDidChange(_ notification: Notification) {
            guard let tv = notification.object as? NSTextView else { return }
            text = tv.string
        }
    }
}

private final class SubmitAwareTextView: NSTextView {
    var onSubmit: (() -> Void)?

    override func keyDown(with event: NSEvent) {
        let isReturn = event.keyCode == 36 || event.keyCode == 76
        if isReturn {
            let modifiers = event.modifierFlags.intersection(.deviceIndependentFlagsMask)
            if modifiers.contains(.shift) {
                insertNewline(nil)
            } else {
                onSubmit?()
            }
            return
        }
        super.keyDown(with: event)
    }
}
