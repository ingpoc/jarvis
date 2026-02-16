import Foundation
import Starscream
import Observation

@available(macOS 14, iOS 17, *)
@Observable
public final class WebSocketClient: WebSocketDelegate {
    public private(set) var isConnected = false
    public private(set) var status: JarvisStatus = .idle
    public private(set) var connectionError: Error?

    public var events: [TimelineEvent] = []
    public var pendingApprovals: [TimelineEvent] = []

    private var ws: WebSocket?
    private var reconnectWork: DispatchWorkItem?
    private let authManager: AuthManager
    private let serverURL: URL
    private var isManualDisconnect = false

    public init(serverURL: URL, authManager: AuthManager = .shared) {
        self.serverURL = serverURL
        self.authManager = authManager
    }

    public func connect() {
        disconnect()
        isManualDisconnect = false

        var request = URLRequest(url: serverURL)
        request.timeoutInterval = 10

        // Add auth header if we have a token
        if let token = authManager.currentToken?.accessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        ws = WebSocket(request: request)
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

    public func sendCommand(action: String, data: [String: Any] = [:]) {
        guard isConnected else { return }

        var payload: [String: Any] = [
            "type": "command",
            "action": action
        ]
        if !data.isEmpty {
            payload["data"] = data
        }

        guard let json = try? JSONSerialization.data(withJSONObject: payload),
              let text = String(data: json, encoding: .utf8) else { return }

        ws?.write(string: text)
    }

    public func getStatus() {
        sendCommand(action: "get_status")
    }

    public func getTimeline(limit: Int = 50) {
        sendCommand(action: "get_timeline", data: ["limit": limit])
    }

    public func approveTask(taskId: String) {
        sendCommand(action: "approve", data: ["task_id": taskId])
    }

    public func denyTask(taskId: String) {
        sendCommand(action: "deny", data: ["task_id": taskId])
    }

    public func runTask(description: String) {
        sendCommand(action: "run_task", data: ["description": description])
    }

    public func sendVoice(text: String) {
        sendCommand(action: "send_voice", data: ["text": text])
    }

    // MARK: - WebSocketDelegate

    public func didReceive(event: WebSocketEvent, client: WebSocket) {
        switch event {
        case .connected:
            DispatchQueue.main.async {
                self.isConnected = true
                self.connectionError = nil
                self.getStatus()
            }

        case .disconnected(let reason, let code):
            DispatchQueue.main.async {
                self.isConnected = false
                if !self.isManualDisconnect {
                    self.scheduleReconnect()
                }
            }

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
        guard let action = json["action"] as? String,
              let data = json["data"] as? [String: Any] else { return }

        if action == "get_status",
           let statusData = try? JSONSerialization.data(withJSONObject: data),
           let resp = try? JSONDecoder().decode(JarvisStatusResponse.self, from: statusData) {
            status = resp.status
        }
    }

    // MARK: - Reconnect

    private func scheduleReconnect() {
        reconnectWork?.cancel()
        let work = DispatchWorkItem { [weak self] in
            self?.connect()
        }
        reconnectWork = work
        DispatchQueue.main.asyncAfter(deadline: .now() + 5, execute: work)
    }
}
