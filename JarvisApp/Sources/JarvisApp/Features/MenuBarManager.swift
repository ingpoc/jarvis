import AppKit
import OSLog

// MARK: - Quick Action Enum

enum QuickAction: String, CaseIterable, Identifiable {
    case toggleMenuBar = "Toggle Menu Bar"
    case refresh = "Refresh Status"
    case showTimeline = "Show Timeline"
    case showCommandCenter = "Show Command Center"
    case showApprovals = "Show Approvals"
    case runTests = "Run Tests"
    case buildProject = "Build Project"
    case gitStatus = "Git Status"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .toggleMenuBar: return "menubar.rectangle"
        case .refresh: return "arrow.clockwise"
        case .showTimeline: return "clock.arrow.circlepath"
        case .showCommandCenter: return "chart.bar.doc.horizontal"
        case .showApprovals: return "checkmark.circle"
        case .runTests: return "testtube.2"
        case .buildProject: return "hammer"
        case .gitStatus: return "branch"
        }
    }
}

// MARK: - Menu Bar Manager

@MainActor
@Observable
final class MenuBarManager {
    static let shared = MenuBarManager()

    private let logger = Logger(subsystem: "com.jarvis.app", category: "MenuBarManager")

    // MARK: - Callbacks

    var onToggleMenuBar: (() -> Void)?
    var onQuickAction: ((QuickAction) -> Void)?

    // MARK: - Initialization

    private init() {
        // Hotkey registration deferred to app launch
    }

    // MARK: - Public API

    func registerGlobalHotkeys() {
        // Use NSHotkey or NSEvent monitoring instead of Carbon
        logger.debug("Global hotkeys: Using Cmd+Shift for toggles")
    }

    func unregisterGlobalHotkeys() {
        // Clean up hotkey registrations
    }

    func installHotKeyHandler() {
        // Install local event monitor for keyboard shortcuts
        NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            guard let self = self else { return event }

            // Cmd+Shift+J to toggle menu
            if event.modifierFlags.contains([.command, .shift]) && event.keyCode == 38 {
                self.onToggleMenuBar?()
            }

            return event
        }
    }

    // MARK: - Quick Actions Execution

    func executeQuickAction(_ action: QuickAction, webSocket: any WebSocketClientProtocol) async {
        logger.info("Executing quick action: \(action.rawValue)")

        switch action {
        case .toggleMenuBar:
            onToggleMenuBar?()

        case .refresh:
            await refreshStatus(webSocket)

        case .showTimeline, .showCommandCenter, .showApprovals:
            onQuickAction?(action)

        case .runTests, .buildProject, .gitStatus:
            await sendCommand(action, webSocket: webSocket)
        }
    }

    private func refreshStatus(_ webSocket: any WebSocketClientProtocol) async {
        try? await webSocket.sendWithoutResponse(action: "get_status", data: nil)
        try? await webSocket.sendWithoutResponse(action: "get_containers", data: nil)
    }

    private func sendCommand(_ action: QuickAction, webSocket: any WebSocketClientProtocol) async {
        let commandAction: String
        switch action {
        case .runTests:
            commandAction = "run_tests"
        case .buildProject:
            commandAction = "build_project"
        case .gitStatus:
            commandAction = "git_status"
        default:
            return
        }

        do {
            try await webSocket.sendWithoutResponse(action: commandAction, data: nil)
        } catch {
            logger.error("Failed to send command \(commandAction): \(error.localizedDescription)")
        }
    }
}
