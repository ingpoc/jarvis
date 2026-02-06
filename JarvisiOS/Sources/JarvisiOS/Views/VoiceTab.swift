import SwiftUI

struct VoiceTab: View {
    @State private var isRecording = false
    @State private var transcript = ""

    var body: some View {
        NavigationStack {
            VStack(spacing: 32) {
                VStack(spacing: 8) {
                    Text("Voice Command")
                        .font(.system(size: 20, weight: .semibold))

                    Text("Hold button to speak")
                        .font(.system(size: 14))
                        .foregroundStyle(.secondary)
                }

                Spacer()

                VoiceRecordingButton(
                    isRecording: $isRecording,
                    transcript: $transcript
                )

                if !transcript.isEmpty {
                    VStack(spacing: 8) {
                        Text("You said:")
                            .font(.system(size: 12))
                            .foregroundStyle(.secondary)

                        Text(transcript)
                            .font(.system(size: 16))
                            .multilineTextAlignment(.center)
                    }
                    .padding()
                    .background(Color(PlatformColor.secondarySystemGroupedBackground))
                    .cornerRadius(10)
                }

                Spacer()
            }
            .padding()
            .navigationTitle("Voice")
        }
    }
}

struct VoiceRecordingButton: View {
    @Binding var isRecording: Bool
    @Binding var transcript: String

    var body: some View {
        ZStack {
            if isRecording {
                Circle()
                    .fill(Color.red.opacity(0.2))
                    .frame(width: 160, height: 160)
                    .scaleEffect(isRecording ? 1.2 : 1.0)
                    .animation(.easeInOut(duration: 1.0).repeatForever(autoreverses: true), value: isRecording)
            }

            Button(action: toggleRecording) {
                ZStack {
                    Circle()
                        .fill(isRecording ? Color.red : Color.accentColor)
                        .frame(width: 100, height: 100)

                    Image(systemName: isRecording ? "stop.fill" : "mic.fill")
                        .font(.system(size: 32))
                        .foregroundStyle(.white)
                }
            }
            .buttonStyle(.plain)
        }
        .onLongPressGesture(minimumDuration: 0, pressing: { pressing in
            if pressing && !isRecording {
                isRecording = true
                startRecording()
            } else if !pressing && isRecording {
                isRecording = false
                stopRecording()
            }
        }, perform: {})
    }

    private func toggleRecording() {
        isRecording.toggle()
    }

    private func startRecording() {
        #if os(iOS)
        let generator = UIImpactFeedbackGenerator(style: .medium)
        generator.impactOccurred()
        #endif
    }

    private func stopRecording() {
        #if os(iOS)
        let generator = UIImpactFeedbackGenerator(style: .light)
        generator.impactOccurred()
        #endif

        transcript = "Run the test suite"
    }
}
