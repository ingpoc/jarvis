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
        switch AVCaptureDevice.authorizationStatus(for: .audio) {
        case .authorized:
            return true
        case .notDetermined:
            return await withCheckedContinuation { continuation in
                AVCaptureDevice.requestAccess(for: .audio) { granted in
                    continuation.resume(returning: granted)
                }
            }
        case .denied, .restricted:
            return false
        @unknown default:
            return false
        }
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
        guard let url = recordingURL else { return }

        Task {
            #if os(macOS)
            let outcome = await Task.detached(priority: .userInitiated) { [self] in
                transcribeWithMLXWhisper(audioURL: url)
            }.value
            await MainActor.run {
                switch outcome {
                case .success(let text):
                    let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
                    if !trimmed.isEmpty {
                        transcript = trimmed
                        onTranscript(trimmed)
                    } else {
                        error = NSError(
                            domain: "VoiceRecorder",
                            code: -3,
                            userInfo: [NSLocalizedDescriptionKey: "No speech detected"]
                        )
                    }
                case .failure(let transcribeError):
                    error = transcribeError
                }
            }
            #else
            await MainActor.run {
                error = NSError(
                    domain: "VoiceRecorder",
                    code: -4,
                    userInfo: [NSLocalizedDescriptionKey: "Local MLX Whisper transcription is only available on macOS"]
                )
            }
            #endif
            cleanupRecording()
        }
    }

    #if os(macOS)
    private struct MLXWhisperResult: Decodable {
        let ok: Bool
        let text: String?
        let error: String?
    }

    private func resolvePythonExecutable() -> String {
        if let configured = ProcessInfo.processInfo.environment["JARVIS_PYTHON_BIN"],
           !configured.isEmpty,
           FileManager.default.isExecutableFile(atPath: configured) {
            return configured
        }

        if let virtualEnv = ProcessInfo.processInfo.environment["VIRTUAL_ENV"], !virtualEnv.isEmpty {
            let venvPython = URL(fileURLWithPath: virtualEnv)
                .appendingPathComponent("bin")
                .appendingPathComponent("python")
                .path
            if FileManager.default.isExecutableFile(atPath: venvPython) {
                return venvPython
            }
        }

        if let found = findVenvPython(from: FileManager.default.currentDirectoryPath) {
            return found
        }

        if let executablePath = Bundle.main.executableURL?.path,
           let found = findVenvPython(from: executablePath) {
            return found
        }

        return "/usr/bin/python3"
    }

    private func findVenvPython(from path: String) -> String? {
        var dirURL = URL(fileURLWithPath: path)
        var isDirectory: ObjCBool = false
        if !FileManager.default.fileExists(atPath: dirURL.path, isDirectory: &isDirectory) {
            return nil
        }
        if !isDirectory.boolValue {
            dirURL.deleteLastPathComponent()
        }

        while true {
            let candidate = dirURL
                .appendingPathComponent(".venv")
                .appendingPathComponent("bin")
                .appendingPathComponent("python")
                .path
            if FileManager.default.isExecutableFile(atPath: candidate) {
                return candidate
            }
            let parent = dirURL.deletingLastPathComponent()
            if parent.path == dirURL.path {
                break
            }
            dirURL = parent
        }
        return nil
    }

    private func transcribeWithMLXWhisper(audioURL: URL) -> Result<String, Error> {
        let script = #"""
import json
import os
import sys

audio_path = sys.argv[1]
model = os.environ.get("JARVIS_MLX_WHISPER_MODEL", "mlx-community/whisper-tiny")

try:
    import mlx_whisper
except Exception as exc:
    print(json.dumps({"ok": False, "error": f"mlx_whisper import failed: {exc}"}))
    sys.exit(0)

try:
    result = mlx_whisper.transcribe(audio_path, path_or_hf_repo=model)
    text = (result.get("text") or "").strip()
    print(json.dumps({"ok": True, "text": text}))
except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc)}))
"""#

        let process = Process()
        process.executableURL = URL(fileURLWithPath: resolvePythonExecutable())
        process.arguments = ["-c", script, audioURL.path]
        process.environment = ProcessInfo.processInfo.environment

        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()
        process.standardOutput = stdoutPipe
        process.standardError = stderrPipe

        do {
            try process.run()
            process.waitUntilExit()
        } catch {
            return .failure(
                NSError(
                    domain: "VoiceRecorder",
                    code: -5,
                    userInfo: [NSLocalizedDescriptionKey: "Failed to start Python transcription process: \(error.localizedDescription)"]
                )
            )
        }

        let stdoutData = stdoutPipe.fileHandleForReading.readDataToEndOfFile()
        let stderrData = stderrPipe.fileHandleForReading.readDataToEndOfFile()
        let stdout = String(data: stdoutData, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let stderr = String(data: stderrData, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""

        guard !stdout.isEmpty else {
            return .failure(
                NSError(
                    domain: "VoiceRecorder",
                    code: -6,
                    userInfo: [
                        NSLocalizedDescriptionKey: "Transcription produced no output",
                        "stderr": stderr
                    ]
                )
            )
        }

        if let data = stdout.data(using: .utf8),
           let payload = try? JSONDecoder().decode(MLXWhisperResult.self, from: data) {
            if payload.ok {
                return .success(payload.text ?? "")
            }
            return .failure(
                NSError(
                    domain: "VoiceRecorder",
                    code: -7,
                    userInfo: [
                        NSLocalizedDescriptionKey: payload.error ?? "Unknown MLX Whisper error",
                        "stderr": stderr
                    ]
                )
            )
        }

        return .success(stdout)
    }
    #endif

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
