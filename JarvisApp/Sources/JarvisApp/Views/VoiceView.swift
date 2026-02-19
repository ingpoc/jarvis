import SwiftUI
import AVFoundation
import JarvisClient

/// Voice View: Push-to-talk voice commands
/// Design: Single prominent action, clear feedback
struct VoiceView: View {
    let isActive: Bool
    @State private var isRecording = false
    @State private var transcript = ""
    @State private var lastCommand = ""
    @State private var voiceRecorder: VoiceRecorder?
    @State private var hasRequestedPermission = false
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
                transcript: $transcript,
                lastCommand: $lastCommand
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
        .onChange(of: isActive) { active in
            if active && !hasRequestedPermission {
                requestMicrophonePermission()
                hasRequestedPermission = true
            }
        }
    }

    private func requestMicrophonePermission() {
        // macOS does not support AVAudioSession. Microphone permission is managed
        // via AVCaptureDevice.
        AVCaptureDevice.requestAccess(for: .audio) { _ in }
    }
}

// MARK: - Voice Button

struct VoiceButton: View {
    @Binding var isRecording: Bool
    @Binding var transcript: String
    @Binding var lastCommand: String

    @State private var pulseScale: CGFloat = 1.0
    @State private var voiceRecorder: VoiceRecorder?
    private static let speechSynthesizer = AVSpeechSynthesizer()

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
        Task {
            // Request microphone permission
            let recorder = VoiceRecorder { transcript in
                Task { @MainActor in
                    self.transcript = transcript
                    sendTranscript(transcript)
                }
            }

            let hasPermission = await recorder.requestMicrophonePermission()
            guard hasPermission else {
                return
            }

            do {
                try recorder.startRecording()
                self.voiceRecorder = recorder
            } catch {
                print("Failed to start recording: \(error)")
            }
        }
    }

    private func stopRecording() {
        voiceRecorder?.stopRecording()
        isRecording = false
        pulseScale = 1.0
    }

    private func sendTranscript(_ text: String) {
        lastCommand = text
        Task { @MainActor in
            do {
                let response = try await WebSocketClient.shared.sendVoice(text: text)
                if let reply = response.reply?.trimmingCharacters(in: .whitespacesAndNewlines),
                   !reply.isEmpty {
                    speak(reply)
                }
            } catch {
                speak("I could not process that voice command.")
            }
        }
    }

    private func speak(_ text: String) {
        let utterance = AVSpeechUtterance(string: text)
        utterance.rate = AVSpeechUtteranceDefaultSpeechRate * 0.9
        utterance.pitchMultiplier = 1.0
        utterance.volume = 1.0
        Self.speechSynthesizer.stopSpeaking(at: .immediate)
        Self.speechSynthesizer.speak(utterance)
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
