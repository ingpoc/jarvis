import Foundation
import Observation

@Observable
final class WebSocketClient {
    var isConnected = false
    var status: JarvisStatus = .idle
    var events: [TimelineEvent] = []
    var pendingApprovals: [TimelineEvent] = []

    private var task: URLSessionWebSocketTask?
    private var session: URLSession = .shared
    private let url = URL(string: "ws://127.0.0.1:9847")!
    private var reconnectWork: DispatchWorkItem?

    func connect() {
        disconnect()
        task = session.webSocketTask(with: url)
        task?.resume()
        isConnected = true
        receiveLoop()
        sendCommand(action: "get_status")
    }

    func disconnect() {
        reconnectWork?.cancel()
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

    private func receiveLoop() {
        task?.receive { [weak self] result in
            guard let self else { return }
            switch result {
            case .success(let message):
                self.handleMessage(message)
                self.receiveLoop()
            case .failure:
                DispatchQueue.main.async {
                    self.isConnected = false
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
    }

    private func handleResponse(_ json: [String: Any]) {
        guard let action = json["action"] as? String else { return }
        if action == "get_status", let data = json["data"] as? [String: Any] {
            if let statusData = try? JSONSerialization.data(withJSONObject: data),
               let resp = try? JSONDecoder().decode(JarvisStatusResponse.self, from: statusData) {
                status = resp.status
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
