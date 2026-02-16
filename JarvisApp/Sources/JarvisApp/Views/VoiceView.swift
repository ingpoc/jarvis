import SwiftUI
import AVFoundation

/// Voice View: Push-to-talk voice commands
/// Design: Single prominent action, clear feedback
struct VoiceView: View {
    @State private var isRecording = false
    @State private var transcript = ""
    @State private var lastCommand = ""

    var body: some View {
        VStack(spacing: 32) {
            VStack(spacing: 8) {
                Text("Voice Command")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(.primary)

                Text("Hold spacebar or click to speak")
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)
            }

            Spacer()

            // Voice Button
            VoiceButton(
                isRecording: $isRecording,
                transcript: $transcript
            )

            // Transcript Display
            if !transcript.isEmpty {
                VStack(spacing: 8) {
                    Text("You said:")
                        .font(.system(size: 11))
                        .foregroundStyle(.tertiary)

                    Text(transcript)
                        .font(.system(size: 14))
                        .foregroundStyle(.primary)
                        .multilineTextAlignment(.center)
                }
                .padding(.horizontal, 32)
            }

            // Last Command
            if !lastCommand.isEmpty {
                VStack(spacing: 8) {
                    Text("Last command:")
                        .font(.system(size: 11))
                        .foregroundStyle(.tertiary)

                    Text(lastCommand)
                        .font(.system(size: 12))
                        .foregroundStyle(.secondary)
                }
                .padding(.horizontal, 32)
            }

            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(nsColor: .textBackgroundColor))
        .onAppear {
            requestMicrophonePermission()
        }
    }

    private func requestMicrophonePermission() {
        AVAudioSession.sharedInstance().requestRecordPermission { _ in }
    }
}

// MARK: - Voice Button

struct VoiceButton: View {
    @Binding var isRecording: Bool
    @Binding var transcript: String

    @State private var pulseScale: CGFloat = 1.0

    var body: some View {
        ZStack {
            // Pulse effect
            if isRecording {
                Circle()
                    .fill(Color.red.opacity(0.2))
                    .frame(width: 120, height: 120)
                    .scaleEffect(pulseScale)
                    .onAppear {
                        withAnimation(.easeInOut(duration: 1.0).repeatForever(autoreverses: true)) {
                            pulseScale = 1.3
                        }
                    }
            }

            // Main button
            Button(action: toggleRecording) {
                ZStack {
                    Circle()
                        .fill(isRecording ? Color.red : Color.accentColor)
                        .frame(width: 80, height: 80)

                    Image(systemName: isRecording ? "stop.fill" : "mic.fill")
                        .font(.system(size: 28))
                        .foregroundStyle(.white)
                }
            }
            .buttonStyle(.plain)
        }
        .onTapGesture {
            toggleRecording()
        }
    }

    private func toggleRecording() {
        isRecording.toggle()

        if isRecording {
            startRecording()
        } else {
            stopRecording()
        }
    }

    private func startRecording() {
        // TODO: Implement actual recording
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
            if isRecording {
                transcript = "Run the test suite"
                stopRecording()
            }
        }
    }

    private func stopRecording() {
        isRecording = false
        pulseScale = 1.0
        // TODO: Send transcript to Jarvis
    }
}

// MARK: - Voice Commands Reference

struct VoiceCommandsReference: View {
    private let commands = [
        ("Run tests", "Execute the test suite"),
        ("Build project", "Compile and build"),
        ("What's the status", "Get current status"),
        ("Git status", "Show git status"),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Voice Commands")
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(.tertiary)
                .padding(.horizontal, 4)

            VStack(spacing: 0) {
                ForEach(Array(commands.enumerated()), id: \.offset) { index, command in
                    HStack {
                        Text(command.0)
                            .font(.system(size: 12))
                            .foregroundStyle(.primary)
                        Spacer()
                        Text(command.1)
                            .font(.system(size: 11))
                            .foregroundStyle(.secondary)
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)

                    if index < commands.count - 1 {
                        Divider()
                    }
                }
            }
            .background(Color(nsColor: .controlBackgroundColor))
            .cornerRadius(6)
        }
    }
}
