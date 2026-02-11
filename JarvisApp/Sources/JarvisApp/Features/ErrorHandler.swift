import Foundation
import OSLog

// MARK: - Error Handler

@MainActor
@Observable
final class ErrorHandler {
    static let shared = ErrorHandler()

    private let logger = Logger(subsystem: "com.jarvis.app", category: "ErrorHandler")

    // MARK: - State

    private(set) var lastError: ErrorType?
    private(set) var errorCount: Int = 0

    // MARK: - Public API

    func handle(_ error: Error, context: String = "") {
        logger.error("Error in \(context): \(error.localizedDescription)")

        lastError = ErrorType(
            error: error,
            context: context,
            timestamp: Date()
        )
        errorCount += 1

        // Show user notification for critical errors
        if isErrorCritical(error) {
            notifyUser(error)
        }
    }

    func clearError() {
        lastError = nil
    }

    func getLastError() -> ErrorType? {
        lastError
    }

    // MARK: - Private Methods

    private func isErrorCritical(_ error: Error) -> Bool {
        // Check if it's a WebSocket error (exclude connectionClosed)
        if let wsError = error as? WebSocketError {
            if case .connectionClosed = wsError {
                return false
            }
            return true
        }
        // Check if it has a recovery suggestion (common in LocalizedError)
        if let localizedError = error as? LocalizedError {
            return localizedError.recoverySuggestion != nil
        }
        return false
    }

    private func notifyUser(_ error: Error) {
        // Trigger notification through NSUserNotification
        // Implementation deferred to when notification system is set up
        logger.info("User notified of error: \(error.localizedDescription)")
    }
}

// MARK: - Error Type

struct ErrorType: Identifiable {
    let id = UUID()
    let error: Error
    let context: String
    let timestamp: Date

    var recoverySuggestion: String? {
        (error as? LocalizedError)?.recoverySuggestion
    }

    var description: String {
        error.localizedDescription
    }

    var isRecoverable: Bool {
        recoverySuggestion != nil
    }
}

// MARK: - Error Categories

enum ErrorCategory: String {
    case network = "Network"
    case websocket = "WebSocket"
    case parsing = "Data Parsing"
    case userAction = "User Action"
    case system = "System"
    case unknown = "Unknown"
}
