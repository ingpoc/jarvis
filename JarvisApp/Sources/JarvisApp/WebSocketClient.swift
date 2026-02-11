import Foundation
import Observation
import OSLog

@Observable
final class WebSocketClient {
    var isConnected = false
    var status: JarvisStatus = .idle
    var events: [TimelineEvent] = []
    var pendingApprovals: [TimelineEvent] = []
    var containers: [ContainerInfo] = []
    var activeTasks: [TaskProgress] = []
    var isLoading = false
    var lastError: String?

    private var task: URLSessionWebSocketTask?
    private var session: URLSession = .shared
    private let url: URL
    private var reconnectWork: DispatchWorkItem?
    private let maxEvents = 200
    private let logger = Logger(subsystem: "com.jarvis.app", category: "WebSocket")

    init() {
        guard let url = URL(string: "ws://127.0.0.1:9847") else {
            fatalError("Invalid WebSocket URL configuration: ws://127.0.0.1:9847")
        }
        self.url = url
    }

    func connect() {
        disconnect()
        task = session.webSocketTask(with: url)
        task?.resume()
        DispatchQueue.main.async { [weak self] in
            self?.isConnected = true
        }
        receiveLoop()
        sendCommand(action: "get_status")
    }

    func disconnect() {
        reconnectWork?.cancel()
        task?.cancel(with: .goingAway, reason: nil)
        task = nil
        DispatchQueue.main.async { [weak self] in
            self?.isConnected = false
        }
    }

    func sendCommand(action: String, data: [String: Any] = [:]) {
        var payload: [String: Any] = [
            "type": "command",
            "action": action
        ]
        if !data.isEmpty {
            payload["data"] = data
        }
        guard let json = try? JSONSerialization.data(withJSONObject: payload),
              let text = String(data: json, encoding: .utf8) else { return }
        task?.send(.string(text)) { [weak self] error in
            if let error = error {
                self?.logger.error("WebSocket send error: \(error.localizedDescription)")
                DispatchQueue.main.async {
                    self?.isConnected = false
                    self?.lastError = "Send failed: \(error.localizedDescription)"
                }
            }
        }
    }

    func refreshContainers() async {
        isLoading = true
        defer { isLoading = false }
        sendCommand(action: "get_containers")
    }

    private func receiveLoop() {
        task?.receive { [weak self] result in
            guard let self else { return }
            switch result {
            case .success(let message):
                self.handleMessage(message)
                self.receiveLoop()
            case .failure(let error):
                self.logger.error("WebSocket receive error: \(error.localizedDescription)")
                DispatchQueue.main.async {
                    self.isConnected = false
                    self.lastError = "Connection error: \(error.localizedDescription)"
                    self.scheduleReconnect()
                }
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
            // O(1) append instead of O(n) insert
            events.append(event)
            if events.count > maxEvents {
                events.removeFirst(events.count - maxEvents)
            }

            if event.eventType == "approval_needed" {
                pendingApprovals.append(event)
                if pendingApprovals.count > 50 {
                    pendingApprovals.removeFirst(pendingApprovals.count - 50)
                }
                // Send notification for approval
                Task { @MainActor in
                    NotificationManager.shared.notifyApprovalNeeded(
                        summary: event.summary,
                        taskId: event.taskId ?? event.id
                    )
                }
            }
        } catch {
            logger.error("Failed to decode TimelineEvent: \(error.localizedDescription)")
            lastError = "Invalid event data from server"
        }
    }

    private func handleResponse(_ json: [String: Any]) {
        guard let action = json["action"] as? String else { return }
        if action == "get_status", let data = json["data"] as? [String: Any] {
            if let statusData = try? JSONSerialization.data(withJSONObject: data),
               let resp = try? JSONDecoder().decode(JarvisStatusResponse.self, from: statusData) {
                status = resp.status
            }
        }
        if action == "get_containers", let data = json["data"] as? [String: Any] {
            if let containersData = try? JSONSerialization.data(withJSONObject: data),
               let resp = try? JSONDecoder().decode(ContainersResponse.self, from: containersData) {
                containers = resp.containers
            }
        }
    }

    private func scheduleReconnect() {
        reconnectWork?.cancel()
        let work = DispatchWorkItem { [weak self] in
            self?.connect()
        }
        reconnectWork = work
        DispatchQueue.main.asyncAfter(deadline: .now() + 5, execute: work)
    }
}
