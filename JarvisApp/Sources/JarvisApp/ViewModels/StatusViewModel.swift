import Foundation
import Observation
import OSLog

// MARK: - Status ViewModel

@Observable
@MainActor
final class StatusViewModel {
    // MARK: - Dependencies

    private let webSocket: WebSocketClientProtocol
    private let logger = Logger(subsystem: "com.jarvis.app", category: "StatusViewModel")

    // MARK: - Output

    var status: JarvisStatus = .idle
    var currentSession: String?
    var currentFeature: String?
    var uptime: String?
    var isConnected = false
    var errorMessage: String?

    // MARK: - Initialization

    init(webSocket: WebSocketClientProtocol) {
        self.webSocket = webSocket
        observeWebSocket()
    }

    // MARK: - Public API

    func refreshStatus() async {
        isConnected = webSocket.connectionState == .connected
        guard isConnected else {
            errorMessage = "Not connected to server"
            return
        }

        do {
            let response: JarvisStatusResponse = try await webSocket.send(
                action: "get_status",
                data: nil,
                timeout: 10
            )
            status = response.status
            currentSession = response.currentSession
            currentFeature = response.currentFeature
            uptime = formatUptime(response.uptime)
            errorMessage = nil
        } catch {
            logger.error("Failed to refresh status: \(error.localizedDescription)")
            errorMessage = "Failed to refresh status"
        }
    }

    // MARK: - Private Methods

    private func observeWebSocket() {
        // Update connection state when socket changes
        // Note: Since WebSocketClient already updates its @Observable properties,
        // we just need to reflect connection state
        isConnected = webSocket.connectionState == .connected
    }

    private func formatUptime(_ seconds: Double?) -> String? {
        guard let seconds = seconds, seconds > 0 else { return nil }

        let hours = Int(seconds) / 3600
        let minutes = Int(seconds) % 3600 / 60
        let secs = Int(seconds) % 60

        if hours > 0 {
            return "\(hours)h \(minutes)m \(secs)s"
        } else if minutes > 0 {
            return "\(minutes)m \(secs)s"
        } else {
            return "\(secs)s"
        }
    }
}
