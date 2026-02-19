import Foundation
import Starscream
import Observation

public enum WebSocketError: LocalizedError {
    case notConnected
    case timeout
    case invalidResponse

    public var errorDescription: String? {
        switch self {
        case .notConnected: return "WebSocket is not connected"
        case .timeout: return "Request timed out"
        case .invalidResponse: return "Invalid response from server"
        }
    }
}

@available(macOS 14, iOS 17, *)
@Observable
public final class JarvisWebSocketClient: Starscream.WebSocketDelegate {
    public private(set) var isConnected = false
    public private(set) var status: JarvisStatus = .idle
    public private(set) var connectionError: Error?

    public var events: [TimelineEvent] = []
    public var pendingApprovals: [TimelineEvent] = []

    private var ws: Starscream.WebSocket?
    private var reconnectWork: DispatchWorkItem?
    private let authManager: AuthManager
    private let serverURL: URL
    private var isManualDisconnect = false
    private var reconnectAttempts = 0
    private let baseReconnectDelay: TimeInterval = 1.0
    private let maxReconnectDelay: TimeInterval = 60.0

    // Request/Response correlation
    private var pendingResponses: [String: CheckedContinuation<[String: Any], Error>] = [:]
    private let responseTimeout: TimeInterval = 30.0

    // Thread-safe singleton
    public static let shared: JarvisWebSocketClient = {
        // Use AuthManager's serverURL - it handles defaults and loading
        let auth = AuthManager.shared
        return JarvisWebSocketClient(serverURL: auth.serverURL, authManager: auth)
    }()

    private init(serverURL: URL, authManager: AuthManager = .shared) {
        self.serverURL = serverURL
        self.authManager = authManager
    }

    public func connect() {
        disconnect()
        isManualDisconnect = false

        var request = URLRequest(url: serverURL)
        request.timeoutInterval = 10

        // Add auth header if we have a token
        // Use current token synchronously for initial connection
        // Token refresh will happen on next connection attempt if expired
        if let token = authManager.currentToken, !token.isExpired {
            request.setValue("Bearer \(token.accessToken)", forHTTPHeaderField: "Authorization")
        }

        ws = Starscream.WebSocket(request: request)
        ws?.delegate = self
        ws?.connect()
    }

    // Async version that ensures token is refreshed before connecting
    public func connectWithValidToken() async throws {
        // This will trigger refresh if needed
        let token = try await authManager.getValidToken()

        disconnect()
        isManualDisconnect = false

        var request = URLRequest(url: serverURL)
        request.timeoutInterval = 10
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        ws = Starscream.WebSocket(request: request)
        ws?.delegate = self
        ws?.connect()
    }

    public func disconnect() {
        isManualDisconnect = true
        reconnectWork?.cancel()
        ws?.disconnect()
        ws = nil
        isConnected = false
    }

    // MARK: - Commands

    private func sendCommand(action: String, data: [String: Sendable] = [:]) -> String? {
        guard isConnected else { return nil }

        let requestId = UUID().uuidString
        var payload: [String: Sendable] = [
            "type": "command",
            "action": action,
            "request_id": requestId
        ]
        if !data.isEmpty {
            payload["data"] = data
        }

        guard let json = try? JSONSerialization.data(withJSONObject: payload, options: [.fragmentsAllowed]),
              let text = String(data: json, encoding: .utf8) else { return nil }

        ws?.write(string: text)
        return requestId
    }

    private func sendCommandAndWait(action: String, data: [String: Sendable] = [:]) async throws -> [String: Any] {
        guard let requestId = sendCommand(action: action, data: data) else {
            throw WebSocketError.notConnected
        }

        return try await withCheckedThrowingContinuation { continuation in
            pendingResponses[requestId] = continuation

            Task {
                try? await Task.sleep(nanoseconds: UInt64(responseTimeout * 1_000_000_000))
                if pendingResponses[requestId] != nil {
                    pendingResponses.removeValue(forKey: requestId)
                    continuation.resume(throwing: WebSocketError.timeout)
                }
            }
        }
    }

    public func getStatus() async throws -> JarvisStatus {
        let response = try await sendCommandAndWait(action: "get_status")
        guard let statusData = try? JSONSerialization.data(withJSONObject: response["data"] as? [String: Any] ?? [:]),
              let resp = try? JSONDecoder().decode(JarvisStatusResponse.self, from: statusData) else {
            throw WebSocketError.invalidResponse
        }
        return resp.status
    }

    public func getTimeline(limit: Int = 50) async throws -> [TimelineEvent] {
        let response = try await sendCommandAndWait(action: "get_timeline", data: ["limit": limit])
        guard let eventsData = response["events"] as? [[String: Any]] else {
            throw WebSocketError.invalidResponse
        }
        return eventsData.compactMap { data in
            guard let eventData = try? JSONSerialization.data(withJSONObject: data),
                  let event = try? JSONDecoder().decode(TimelineEvent.self, from: eventData) else {
                return nil
            }
            return event
        }
    }

    public func approveTask(taskId: String) async throws -> Bool {
        let response = try await sendCommandAndWait(action: "approve", data: ["task_id": taskId])
        return (response["success"] as? Bool) ?? false
    }

    public func denyTask(taskId: String) async throws -> Bool {
        let response = try await sendCommandAndWait(action: "deny", data: ["task_id": taskId])
        return (response["success"] as? Bool) ?? false
    }

    public func runTask(description: String) async throws -> String {
        let response = try await sendCommandAndWait(action: "run_task", data: ["description": description])
        guard let taskId = response["task_id"] as? String else {
            throw WebSocketError.invalidResponse
        }
        return taskId
    }

    public func sendVoice(text: String) async throws -> Bool {
        let response = try await sendCommandAndWait(action: "send_voice", data: ["text": text])
        return (response["success"] as? Bool) ?? false
    }

    public func didReceive(event: WebSocketEvent, client: Starscream.WebSocketClient) {
        switch event {
        case .connected:
            DispatchQueue.main.async {
                self.isConnected = true
                self.connectionError = nil
                self.reconnectAttempts = 0
                Task {
                    try? await self.getStatus()
                }
            }

        case .disconnected(let reason, let code):
            DispatchQueue.main.async {
                self.isConnected = false
                if !self.isManualDisconnect {
                    self.scheduleReconnect()
                }
            }
            _ = reason
            _ = code

        case .text(let text):
            handleMessage(text)

        case .error(let error):
            DispatchQueue.main.async {
                self.connectionError = error
                self.isConnected = false
            }

        default:
            break
        }
    }

    // MARK: - Message Handling

    private func handleMessage(_ text: String) {
        guard let data = text.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = json["type"] as? String else { return }

        DispatchQueue.main.async {
            switch type {
            case "auth_success":
                // Successfully authenticated
                break

            case "event":
                self.handleEvent(json["data"] as? [String: Any] ?? json)

            case "response":
                self.handleResponse(json)

            case "error":
                let errorMsg = (json["data"] as? [String: Any])?["message"] as? String
                self.connectionError = NSError(domain: "JarvisClient", code: -1, userInfo: [
                    NSLocalizedDescriptionKey: errorMsg ?? "Unknown error"
                ])

            default:
                break
            }
        }
    }

    private func handleEvent(_ data: [String: Any]) {
        guard let eventData = try? JSONSerialization.data(withJSONObject: data),
              let event = try? JSONDecoder().decode(TimelineEvent.self, from: eventData) else { return }

        events.insert(event, at: 0)
        if events.count > 200 {
            events = Array(events.prefix(200))
        }

        if event.eventType == "approval_needed" {
            pendingApprovals.insert(event, at: 0)
        }
    }

    private func handleResponse(_ json: [String: Any]) {
        guard let requestId = json["request_id"] as? String else {
            // Handle legacy responses without request_id for backward compatibility
            guard let action = json["action"] as? String,
                  let data = json["data"] as? [String: Any] else { return }

            if action == "get_status",
               let statusData = try? JSONSerialization.data(withJSONObject: data),
               let resp = try? JSONDecoder().decode(JarvisStatusResponse.self, from: statusData) {
                status = resp.status
            }
            return
        }

        // Match response to pending request
        if let continuation = pendingResponses[requestId] {
            pendingResponses.removeValue(forKey: requestId)
            continuation.resume(returning: json)
        }
    }

    // MARK: - Reconnect

    private func scheduleReconnect() {
        reconnectWork?.cancel()
        let delay = calculateReconnectDelay()
        reconnectAttempts += 1
        let work = DispatchWorkItem { [weak self] in
            self?.connect()
        }
        reconnectWork = work
        DispatchQueue.main.asyncAfter(deadline: .now() + delay, execute: work)
    }

    private func calculateReconnectDelay() -> TimeInterval {
        let exponentialDelay = baseReconnectDelay * pow(2.0, Double(reconnectAttempts))
        return min(exponentialDelay, maxReconnectDelay)
    }
}

// Type alias for backward compatibility
public typealias WebSocketClient = JarvisWebSocketClient
