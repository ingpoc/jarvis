import Foundation
import Observation
import OSLog

// MARK: - Connection State

enum ConnectionState: Equatable {
    case disconnected
    case connecting
    case connected
    case reconnecting
}

// MARK: - WebSocket Errors

enum WebSocketError: LocalizedError {
    case notConnected
    case sendFailed(String)
    case receiveFailed(String)
    case invalidResponse(String)
    case requestTimeout
    case decodingFailed(Error)
    case encodingFailed(Error)
    case connectionClosed

    var errorDescription: String? {
        switch self {
        case .notConnected:
            return "Not connected to server"
        case .sendFailed(let msg):
            return "Failed to send: \(msg)"
        case .receiveFailed(let msg):
            return "Failed to receive: \(msg)"
        case .invalidResponse(let msg):
            return "Invalid response: \(msg)"
        case .requestTimeout:
            return "Request timed out"
        case .decodingFailed(let error):
            return "Failed to decode response: \(error.localizedDescription)"
        case .encodingFailed(let error):
            return "Failed to encode request: \(error.localizedDescription)"
        case .connectionClosed:
            return "Connection closed by server"
        }
    }

    var recoverySuggestion: String? {
        switch self {
        case .notConnected, .connectionClosed:
            return "Waiting for automatic reconnection..."
        case .requestTimeout:
            return "Check server status and try again"
        case .sendFailed, .receiveFailed, .invalidResponse:
            return "Retry the action"
        case .decodingFailed, .encodingFailed:
            return "This may be a version mismatch - check for updates"
        }
    }
}

// MARK: - WebSocket Delegate

@MainActor
protocol WebSocketDelegate: AnyObject {
    func connectionStateDidChange(_ state: ConnectionState)
    func didReceiveEvent(_ event: TimelineEvent)
    func didEncounterError(_ error: WebSocketError)
}

// MARK: - WebSocket Protocol

protocol WebSocketClientProtocol: AnyObject {
    var connectionState: ConnectionState { get }
    var delegate: WebSocketDelegate? { get set }
    var events: [TimelineEvent] { get }
    var containers: [ContainerInfo] { get }
    var availableTools: [String] { get }
    var pendingApprovals: [TimelineEvent] { get }
    var status: JarvisStatus { get }

    func connect()
    func disconnect()

    func send<T: Decodable>(
        action: String,
        data: [String: Any]?,
        timeout: TimeInterval
    ) async throws -> T

    func sendWithoutResponse(action: String, data: [String: Any]?) async throws
}

// MARK: - Request Types

private struct PendingRequest {
    let id: String
    let timeout: DispatchTime
    let callback: (Result<Data, Error>) -> Void

    var isExpired: Bool {
        timeout < .now()
    }
}

// Empty type for fire-and-forget requests
private struct EmptyResponse: Decodable {}

// MARK: - WebSocket Client Implementation

@Observable
final class WebSocketClient: WebSocketClientProtocol {
    var connectionState: ConnectionState = .disconnected
    weak var delegate: WebSocketDelegate?

    // Observable state for views
    var isConnected: Bool { connectionState == .connected }
    var status: JarvisStatus = .idle
    var events: [TimelineEvent] = []
    var pendingApprovals: [TimelineEvent] = []
    var containers: [ContainerInfo] = []
    var availableTools: [String] = []
    var activeTasks: [TaskProgress] = []
    var isLoading = false
    var lastError: String?

    private var task: URLSessionWebSocketTask?
    private let session: URLSession = .shared
    private let url: URL
    private var reconnectWork: DispatchWorkItem?

    // Request/Response correlation
    private var pendingRequests: [String: PendingRequest] = [:]
    private let pendingRequestsQueue = DispatchQueue(label: "com.jarvis.pending-requests")
    private let defaultTimeout: TimeInterval = 30.0
    private let maxEvents = 200
    private let logger = Logger(subsystem: "com.jarvis.app", category: "WebSocket")

    init() {
        guard let url = URL(string: "ws://127.0.0.1:9847") else {
            fatalError("Invalid WebSocket URL configuration: ws://127.0.0.1:9847")
        }
        self.url = url
        // Ensure connection attempts start even before the menu window is opened.
        DispatchQueue.main.async { [weak self] in
            self?.connect()
        }
    }

    deinit {
        disconnect()
    }

    // MARK: - Connection

    func connect() {
        guard connectionState != .connected else { return }

        updateState(.connecting)
        reconnectWork?.cancel()
        task?.cancel(with: .goingAway, reason: nil)
        task = nil

        task = session.webSocketTask(with: url)
        task?.resume()

        updateState(.connected)
        receiveLoop()
        print("WebSocket connect() called for \(url.absoluteString)")

        Task {
            try? await sendWithoutResponse(action: "get_status", data: nil)
            try? await sendWithoutResponse(action: "get_available_tools", data: nil)
        }
    }

    func disconnect() {
        updateState(.disconnected)
        reconnectWork?.cancel()
        task?.cancel(with: .goingAway, reason: nil)
        task = nil

        // Fail all pending requests
        pendingRequestsQueue.sync {
            for request in pendingRequests.values {
                request.callback(.failure(WebSocketError.connectionClosed))
            }
            pendingRequests.removeAll()
        }
    }

    // MARK: - Send with Response (New API with correlation)

    func send<T: Decodable>(
        action: String,
        data: [String: Any]? = nil,
        timeout: TimeInterval = 30
    ) async throws -> T {
        guard connectionState == .connected else {
            throw WebSocketError.notConnected
        }

        let requestId = UUID().uuidString

        // Build JSON payload manually (no Codable on [String: Any])
        var payload: [String: Any] = [
            "type": "command",
            "id": requestId,
            "action": action
        ]
        if let data = data {
            payload["data"] = data
        }

        let jsonString: String
        do {
            let jsonData = try JSONSerialization.data(withJSONObject: payload)
            guard let str = String(data: jsonData, encoding: .utf8) else {
                throw WebSocketError.encodingFailed(NSError(domain: "WebSocket", code: -1, userInfo: nil))
            }
            jsonString = str
        } catch {
            throw WebSocketError.encodingFailed(error)
        }

        return try await withCheckedThrowingContinuation { continuation in
            let timeoutTime = DispatchTime.now() + timeout

            pendingRequestsQueue.sync {
                self.pendingRequests[requestId] = PendingRequest(
                    id: requestId,
                    timeout: timeoutTime
                ) { result in
                    switch result {
                    case .success(let data):
                        do {
                            let decoded = try JSONDecoder().decode(T.self, from: data)
                            continuation.resume(returning: decoded)
                        } catch {
                            continuation.resume(throwing: WebSocketError.decodingFailed(error))
                        }
                    case .failure(let error):
                        continuation.resume(throwing: error)
                    }
                }
            }

            task?.send(.string(jsonString)) { [weak self] error in
                guard let self else { return }
                if let error = error {
                    self.logger.error("WebSocket send error: \(error.localizedDescription)")
                    self.pendingRequestsQueue.sync {
                        self.pendingRequests.removeValue(forKey: requestId)?.callback(.failure(WebSocketError.sendFailed(error.localizedDescription)))
                    }
                }
            }

            // Start timeout timer
            Task {
                do {
                    try await Task.sleep(nanoseconds: UInt64(timeout * 1_000_000_000))
                    self.pendingRequestsQueue.sync {
                        if let pending = self.pendingRequests[requestId], !pending.isExpired {
                            self.pendingRequests.removeValue(forKey: requestId)?.callback(.failure(WebSocketError.requestTimeout))
                        }
                    }
                } catch {
                    // Task was cancelled
                }
            }
        }
    }

    func sendWithoutResponse(action: String, data: [String: Any]? = nil) async throws {
        // Fire-and-forget: use EmptyResponse type
        let _: EmptyResponse = try await self.send(action: action, data: data, timeout: 10)
    }

    // MARK: - Legacy API (backward compatibility)

    func sendCommand(action: String, data: [String: Any] = [:]) {
        Task {
            try? await self.sendWithoutResponse(action: action, data: data.isEmpty ? nil : data)
        }
    }

    // MARK: - Receive Loop

    private func receiveLoop() {
        task?.receive { [weak self] result in
            guard let self else { return }

            switch result {
            case .success(let message):
                self.handleMessage(message)
                self.receiveLoop()
            case .failure(let error):
                let ns = error as NSError
                self.logger.error(
                    "WebSocket receive error domain=\(ns.domain, privacy: .public) code=\(ns.code, privacy: .public) desc=\(ns.localizedDescription, privacy: .public)"
                )
                print("WebSocket receive error domain=\(ns.domain) code=\(ns.code) desc=\(ns.localizedDescription)")
                self.handleConnectionError(error)
            }
        }
    }

    private func handleMessage(_ message: URLSessionWebSocketTask.Message) {
        let data: Data
        switch message {
        case .string(let text):
            guard let d = text.data(using: .utf8) else { return }
            data = d
        case .data(let d):
            data = d
        @unknown default:
            return
        }

        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = json["type"] as? String else { return }

        DispatchQueue.main.async {
            switch type {
            case "event":
                self.handleEvent(json["data"] as? [String: Any] ?? json)
            case "response":
                self.handleResponse(json)
            default:
                break
            }
        }
    }

    private func handleEvent(_ data: [String: Any]) {
        guard let eventData = try? JSONSerialization.data(withJSONObject: data) else {
            logger.error("Failed to serialize event data")
            return
        }

        do {
            let event = try JSONDecoder().decode(TimelineEvent.self, from: eventData)
            lastError = nil
            appendEvent(event)

            if event.eventType == "approval_needed" {
                addPendingApproval(event)
                Task { @MainActor in
                    NotificationManager.shared.notifyApprovalNeeded(
                        summary: event.summary,
                        taskId: event.taskId ?? event.id
                    )
                }
            }

            // Index event in Spotlight
            Task { @MainActor in
                SpotlightService.shared.indexEvent(event)
            }

            Task { @MainActor in
                self.delegate?.didReceiveEvent(event)
            }
        } catch {
            logger.error("Failed to decode TimelineEvent: \(error.localizedDescription)")
            lastError = "Invalid event data from server"
        }
    }

    private func handleResponse(_ json: [String: Any]) {
        // First, try to match with pending request by id
        if let requestId = json["id"] as? String {
            pendingRequestsQueue.sync {
                if let pending = pendingRequests[requestId] {
                    pendingRequests.removeValue(forKey: requestId)

                    do {
                        let jsonData = try JSONSerialization.data(withJSONObject: json)
                        pending.callback(.success(jsonData))
                    } catch {
                        pending.callback(.failure(WebSocketError.decodingFailed(error)))
                    }
                    return
                }
            }
        }

        // Legacy handling for action-based responses
        guard let action = json["action"] as? String else { return }
        handleLegacyResponse(action: action, json: json)
    }

    private func handleLegacyResponse(action: String, json: [String: Any]) {
        lastError = nil
        switch action {
        case "get_status":
            if let data = json["data"] as? [String: Any],
               let statusData = try? JSONSerialization.data(withJSONObject: data),
               let resp = try? JSONDecoder().decode(JarvisStatusResponse.self, from: statusData) {
                status = resp.status
            }
        case "get_containers":
            if let data = json["data"] as? [String: Any],
               let containersData = try? JSONSerialization.data(withJSONObject: data),
               let resp = try? JSONDecoder().decode(ContainersResponse.self, from: containersData) {
                containers = resp.containers

                // Index containers in Spotlight
                Task { @MainActor in
                    for container in resp.containers {
                        SpotlightService.shared.indexContainer(container)
                    }
                }
            }
        case "get_available_tools":
            if let data = json["data"] as? [String: Any],
               let tools = data["tools"] as? [String] {
                availableTools = tools
            }
        default:
            break
        }
    }

    // MARK: - State Management

    private func updateState(_ state: ConnectionState) {
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            self.connectionState = state
            if state == .connected {
                self.lastError = nil
            }
            Task { @MainActor in
                self.delegate?.connectionStateDidChange(state)
            }
        }
    }

    private func handleConnectionError(_ error: Error) {
        let ns = error as NSError
        print("handleConnectionError domain=\(ns.domain) code=\(ns.code) desc=\(ns.localizedDescription)")
        updateState(.disconnected)
        lastError = "Connection error: \(error.localizedDescription)"
        scheduleReconnect()
    }

    private func scheduleReconnect() {
        reconnectWork?.cancel()
        updateState(.reconnecting)
        let work = DispatchWorkItem { [weak self] in
            self?.connect()
        }
        reconnectWork = work
        DispatchQueue.main.asyncAfter(deadline: .now() + 5, execute: work)
    }

    // MARK: - Event Management

    private func appendEvent(_ event: TimelineEvent) {
        events.append(event)
        if events.count > maxEvents {
            events.removeFirst(events.count - maxEvents)
        }
    }

    private func addPendingApproval(_ event: TimelineEvent) {
        pendingApprovals.append(event)
        if pendingApprovals.count > 50 {
            pendingApprovals.removeFirst(pendingApprovals.count - 50)
        }
    }
}

// MARK: - Legacy Extensions

extension WebSocketClient {
    func refreshContainers() async {
        isLoading = true
        defer { isLoading = false }
        try? await sendWithoutResponse(action: "get_containers", data: nil)
        try? await sendWithoutResponse(action: "get_available_tools", data: nil)
    }
}
