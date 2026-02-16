import SwiftUI

struct CommandInputView: View {
    @Environment(WebSocketClient.self) private var ws
    @State private var command = ""
    @State private var isSubmitting = false
    @State private var parsedIntent: ParsedIntent?
    @FocusState private var isFocused: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            // Parsed intent confidence display
            if let intent = parsedIntent, !command.isEmpty {
                HStack(spacing: 6) {
                    Image(systemName: intent.iconName)
                        .font(.caption2)
                        .foregroundStyle(intent.confidenceColor)

                    Text(intent.label)
                        .font(.caption2)
                        .foregroundStyle(.secondary)

                    Spacer()

                    // Confidence bar
                    ConfidenceBadge(confidence: intent.confidence)
                }
                .padding(.horizontal, 4)
                .transition(.opacity.combined(with: .move(edge: .bottom)))
            }

            // Command input field
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
                    .onChange(of: command) { _, newValue in
                        parseIntent(newValue)
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
    }

    private func submitCommand() {
        let trimmed = command.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, ws.isConnected else { return }

        isSubmitting = true
        ws.runTask(description: trimmed)
        command = ""
        parsedIntent = nil

        // Reset submitting state after a brief delay
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            isSubmitting = false
        }
    }

    private func parseIntent(_ text: String) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            withAnimation(.easeInOut(duration: 0.15)) {
                parsedIntent = nil
            }
            return
        }

        let lower = trimmed.lowercased()

        // NL intent classification (local heuristic, GLM-backed when available)
        let intent: ParsedIntent
        if lower.hasPrefix("fix ") || lower.contains("bug") || lower.contains("error") {
            intent = ParsedIntent(
                label: "Bug Fix",
                category: .bugfix,
                confidence: lower.hasPrefix("fix ") ? 0.9 : 0.7,
                iconName: "ladybug.fill"
            )
        } else if lower.hasPrefix("add ") || lower.hasPrefix("create ") || lower.hasPrefix("implement ") || lower.hasPrefix("build ") {
            intent = ParsedIntent(
                label: "New Feature",
                category: .feature,
                confidence: 0.85,
                iconName: "plus.circle.fill"
            )
        } else if lower.hasPrefix("refactor ") || lower.contains("clean up") || lower.contains("restructure") {
            intent = ParsedIntent(
                label: "Refactor",
                category: .refactor,
                confidence: 0.8,
                iconName: "arrow.triangle.2.circlepath"
            )
        } else if lower.hasPrefix("test ") || lower.contains("write test") || lower.contains("add test") {
            intent = ParsedIntent(
                label: "Testing",
                category: .test,
                confidence: 0.85,
                iconName: "checkmark.circle"
            )
        } else if lower.hasPrefix("review ") || lower.contains("code review") {
            intent = ParsedIntent(
                label: "Code Review",
                category: .review,
                confidence: 0.8,
                iconName: "eye.fill"
            )
        } else if lower.hasPrefix("deploy ") || lower.contains("release") || lower.contains("publish") {
            intent = ParsedIntent(
                label: "Deploy",
                category: .deploy,
                confidence: 0.75,
                iconName: "paperplane.fill"
            )
        } else {
            intent = ParsedIntent(
                label: "General Task",
                category: .general,
                confidence: 0.5,
                iconName: "hammer.fill"
            )
        }

        withAnimation(.easeInOut(duration: 0.15)) {
            parsedIntent = intent
        }
    }
}

// MARK: - Parsed Intent

struct ParsedIntent {
    let label: String
    let category: IntentCategory
    let confidence: Double
    let iconName: String

    var confidenceColor: Color {
        if confidence >= 0.8 { return .green }
        if confidence >= 0.6 { return .yellow }
        return .orange
    }
}

enum IntentCategory {
    case bugfix, feature, refactor, test, review, deploy, general
}

// MARK: - Confidence Badge

struct ConfidenceBadge: View {
    let confidence: Double

    var body: some View {
        HStack(spacing: 3) {
            Text("\(Int(confidence * 100))%")
                .font(.system(.caption2, design: .monospaced))
                .foregroundStyle(color)

            // Mini bar
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Color.gray.opacity(0.2))
                        .frame(height: 4)

                    RoundedRectangle(cornerRadius: 2)
                        .fill(color)
                        .frame(width: geo.size.width * confidence, height: 4)
                }
            }
            .frame(width: 30, height: 4)
        }
    }

    private var color: Color {
        if confidence >= 0.8 { return .green }
        if confidence >= 0.6 { return .yellow }
        return .orange
    }
}
