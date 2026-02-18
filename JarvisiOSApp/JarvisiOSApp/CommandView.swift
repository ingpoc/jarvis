//
//  CommandView.swift
//  JarvisiOSApp
//
//  Mobile command input with haptic feedback
//

import SwiftUI

struct CommandView: View {
    @State private var commandText = ""
    @State private var isSending = false
    @State private var response = ""
    @State private var showResponse = false

    private let quickCommands = [
        "git status",
        "run tests",
        "build project",
        "check logs",
    ]

    var body: some View {
        NavigationView {
            VStack(spacing: 20) {
                // Command Input
                VStack(alignment: .leading, spacing: 8) {
                    Text("Send Command")
                        .font(.headline)

                    TextField("Enter command...", text: $commandText)
                        .textFieldStyle(.roundedBorder)
                        .autocapitalization(.none)
                        .disabled(isSending)

                    Button(action: sendCommand) {
                        if isSending {
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        } else {
                            Text("Send")
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(commandText.isEmpty ? Color.gray : Color.blue)
                    .foregroundStyle(.white)
                    .cornerRadius(10)
                    .disabled(commandText.isEmpty || isSending)
                }
                .padding()

                // Quick Commands
                VStack(alignment: .leading, spacing: 8) {
                    Text("Quick Commands")
                        .font(.headline)

                    LazyVGrid(columns: [
                        GridItem(.flexible()),
                        GridItem(.flexible())
                    ], spacing: 12) {
                        ForEach(quickCommands, id: \.self) { cmd in
                            Button(cmd) {
                                commandText = cmd
                                sendCommand()
                            }
                            .padding()
                            .background(Color.blue.opacity(0.1))
                            .foregroundStyle(.blue)
                            .cornerRadius(8)
                        }
                    }
                }
                .padding()

                Spacer()

                // Response Sheet
                if showResponse {
                    ScrollView {
                        Text(response)
                            .font(.system(.body, design: .monospaced))
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding()
                    }
                    .background(Color.gray.opacity(0.1))
                    .cornerRadius(10)
                    .padding()
                }
            }
            .navigationTitle("Commands")
        }
    }

    private func sendCommand() {
        guard !commandText.isEmpty else { return }

        isSending = true
        let cmd = commandText
        commandText = ""

        // Simulate command execution
        Task {
            try? await Task.sleep(nanoseconds: 1_000_000_000)
            await MainActor.run {
                response = """
                > \(cmd)

                Command executed successfully.
                Status: 0
                Time: \(Date().formatted(date: .omitted, time: .standard))
                """
                showResponse = true
                isSending = false
            }
        }

        // Haptic feedback
        let generator = UIImpactFeedbackGenerator(style: .medium)
        generator.impactOccurred()
    }
}

#Preview {
    CommandView()
}
