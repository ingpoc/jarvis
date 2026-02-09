import Foundation
import Observation

@Observable
final class WebSocketClient {
    var isConnected = false
    var status: JarvisStatus = .idle
    var events: [TimelineEvent] = []
    var pendingApprovals: [TimelineEvent] = []
    var trustInfo: TrustInfo?
    var budgetInfo: BudgetInfo?
    var currentFeature: String?
    var currentSession: String?
    var lastError: String?

    private var task: URLSessionWebSocketTask?
    private var session: URLSession = .shared
    private let url = URL(string: "ws://127.0.0.1:9847")!
    private var reconnectWork: DispatchWorkItem?
    private var statusTimer: Timer?

    func connect() {
        disconnect()
        task = session.webSocketTask(with: url)
        task?.resume()
        isConnected = true
        lastError = nil
        receiveLoop()
        sendCommand(action: "get_status")

        // Poll status periodically
        statusTimer = Timer.scheduledTimer(withTimeInterval: 10, repeats: true) { [weak self] _ in
            self?.sendCommand(action: "get_status")
        }
    }

    func disconnect() {
        reconnectWork?.cancel()
        statusTimer?.invalidate()
        statusTimer = nil
        task?.cancel(with: .goingAway, reason: nil)
        task = nil
        isConnected = false
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
        task?.send(.string(text)) { _ in }
    }

    func runTask(description: String) {
        sendCommand(action: "run_task", data: ["description": description])
    }

    func approve(taskId: String) {
        sendCommand(action: "approve", data: ["task_id": taskId])
        pendingApprovals.removeAll { ($0.taskId ?? "") == taskId }
    }

    func deny(taskId: String) {
        sendCommand(action: "deny", data: ["task_id": taskId])
        pendingApprovals.removeAll { ($0.taskId ?? "") == taskId }
    }

    private func receiveLoop() {
        task?.receive { [weak self] result in
            guard let self else { return }
            switch result {
            case .success(let message):
                self.handleMessage(message)
                self.receiveLoop()
            case .failure(let error):
                DispatchQueue.main.async {
                    self.isConnected = false
                    self.lastError = error.localizedDescription
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
        guard let eventData = try? JSONSerialization.data(withJSONObject: data),
              let event = try? JSONDecoder().decode(TimelineEvent.self, from: eventData) else { return }

        events.insert(event, at: 0)
        if events.count > 200 {
            events = Array(events.prefix(200))
        }

        if event.eventType == "approval_needed" {
            pendingApprovals.insert(event, at: 0)
        }

        // Update status from events
        switch event.eventType {
        case "task_start":
            status = .building
        case "task_complete":
            status = pendingApprovals.isEmpty ? .completed : .waitingApproval
        case "error":
            status = .error
        case "approval_needed":
            status = .waitingApproval
        default:
            break
        }
    }

    private func handleResponse(_ json: [String: Any]) {
        guard let action = json["action"] as? String else { return }
        if action == "get_status", let data = json["data"] as? [String: Any] {
            if let statusData = try? JSONSerialization.data(withJSONObject: data),
               let resp = try? JSONDecoder().decode(JarvisStatusResponse.self, from: statusData) {
                status = resp.status
                trustInfo = resp.trust
                budgetInfo = resp.budget
                currentFeature = resp.currentFeature
                currentSession = resp.currentSession
            }
        } else if action == "run_task" {
            // Task was queued
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
