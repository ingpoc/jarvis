import AVFoundation
import Foundation
#if canImport(AppKit)
import AppKit
#endif

/// Voice recording utility using AVAudioRecorder
/// Handles microphone permissions, recording state, and audio file management
/// Platform-aware: iOS uses AVAudioSession, macOS uses direct audio recording
@available(macOS 14, iOS 17, *)
public final class VoiceRecorder: NSObject, ObservableObject, AVAudioRecorderDelegate {
    @Published public var isRecording = false
    @Published public var transcript = ""
    @Published public var error: Error?

    private var audioRecorder: AVAudioRecorder?
    private var recordingURL: URL?
    private let onTranscript: (String) -> Void

    // Audio session configuration
    private let sampleRate: Double = 16000.0
    private let channels: UInt32 = 1

    public init(onTranscript: @escaping (String) -> Void) {
        self.onTranscript = onTranscript
        super.init()
    }

    // MARK: - Permission

    public func requestMicrophonePermission() async -> Bool {
        #if os(iOS)
        return await AVAudioSession.sharedInstance().requestRecordPermission { granted in
            return granted
        }
        #else
        // macOS uses permission captured via system prompt on first access
        return true
        #endif
    }

    // MARK: - Recording

    public func startRecording() throws {
        guard !isRecording else { return }

        #if os(iOS)
        // Configure audio session for iOS
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.record, mode: .measurement, options: .duckOthers)
        try session.setActive(true)
        #endif

        // Create temp file for recording
        let tempDir = FileManager.default.temporaryDirectory
        let filename = UUID().uuidString + ".m4a"
        recordingURL = tempDir.appendingPathComponent(filename)

        // Configure recording settings
        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
            AVSampleRateKey: sampleRate,
            AVNumberOfChannelsKey: channels,
            AVEncoderAudioQualityKey: AVAudioQuality.high.rawValue
        ]

        // Create recorder
        audioRecorder = try AVAudioRecorder(url: recordingURL!, settings: settings)
        audioRecorder?.delegate = self
        audioRecorder?.isMeteringEnabled = true
        audioRecorder?.record()

        DispatchQueue.main.async {
            self.isRecording = true
            self.error = nil
        }
    }

    public func stopRecording() {
        guard isRecording else { return }

        audioRecorder?.stop()
        audioRecorder = nil

        #if os(iOS)
        // Deactivate audio session on iOS
        try? AVAudioSession.sharedInstance().setActive(false)
        #endif

        DispatchQueue.main.async {
            self.isRecording = false
        }
    }

    public func cancelRecording() {
        stopRecording()
        cleanupRecording()
    }

    // MARK: - Transcription

    private func transcribeRecording() {
        guard recordingURL != nil else { return }

        // For now, just trigger callback with placeholder
        // Full transcription would integrate with Speech framework or external API
        Task { @MainActor in
            self.transcript = "[Audio recorded - transcription pending]"
            self.onTranscript(self.transcript)
            self.cleanupRecording()
        }
    }

    private func cleanupRecording() {
        if let url = recordingURL {
            try? FileManager.default.removeItem(at: url)
            recordingURL = nil
        }
    }

    // MARK: - AVAudioRecorderDelegate

    public nonisolated func audioRecorderDidFinishRecording(_ recorder: AVAudioRecorder, successfully flag: Bool) {
        if flag {
            transcribeRecording()
        } else {
            DispatchQueue.main.async {
                self.error = NSError(domain: "VoiceRecorder", code: -1, userInfo: [
                    NSLocalizedDescriptionKey: "Recording failed"
                ])
            }
        }
    }

    public nonisolated func audioRecorderEncodeErrorDidOccur(_ recorder: AVAudioRecorder, error: Error?) {
        DispatchQueue.main.async {
            self.isRecording = false
            if let error = error {
                self.error = error
            }
        }
    }
}
