import Foundation
import Observation
import OSLog

// MARK: - Response Types

private struct StopStartResponse: Decodable {
    let success: Bool
}

private struct EmptyResponse: Decodable {}

// MARK: - Container Status Filter

enum ContainerStatusFilter: String, CaseIterable {
    case all
    case running
    case stopped
    case paused

    var displayName: String {
        switch self {
        case .all: return "All Containers"
        case .running: return "Running Only"
        case .stopped: return "Stopped Only"
        case .paused: return "Paused Only"
        }
    }
}

// MARK: - Containers ViewModel

@Observable
@MainActor
final class ContainersViewModel {
    // MARK: - Dependencies

    private let webSocket: WebSocketClientProtocol
    private let persistence: PersistenceManager
    private let logger = Logger(subsystem: "com.jarvis.app", category: "ContainersViewModel")

    // MARK: - Output

    var containers: [ContainerInfo] = []
    var filteredContainers: [ContainerInfo] = []
    var selectedStatus: ContainerStatusFilter = .all
    var isLoading = false
    var errorMessage: String?

    // MARK: - Initialization

    init(webSocket: WebSocketClientProtocol, persistence: PersistenceManager = .shared) {
        self.webSocket = webSocket
        self.persistence = persistence
        observeWebSocket()
        loadFromPersistence()
    }

    // MARK: - Public API

    func refreshContainers() async {
        isLoading = true
        defer { isLoading = false }

        do {
            let response: ContainersResponse = try await webSocket.send(
                action: "get_containers",
                data: nil,
                timeout: 15
            )

            containers = response.containers

            // Persist to disk
            for container in containers {
                persistence.saveContainer(container)
            }

            applyFilter()
            errorMessage = nil
        } catch {
            logger.error("Failed to refresh containers: \(error.localizedDescription)")
            errorMessage = "Failed to refresh containers"
        }
    }

    func stopContainer(_ id: String) async {
        isLoading = true
        defer { isLoading = false }

        do {
            let _: StopStartResponse = try await webSocket.send(
                action: "stop_container",
                data: ["container_id": id],
                timeout: 30
            )

            await refreshContainers()

            // Persist state change
            if let index = containers.firstIndex(where: { $0.id == id }) {
                containers[index].status = "stopped"
                persistence.saveContainer(containers[index])
            }
        } catch {
            logger.error("Failed to stop container: \(error.localizedDescription)")
            errorMessage = "Failed to stop container"
        }
    }

    func startContainer(_ id: String) async {
        isLoading = true
        defer { isLoading = false }

        do {
            let _: StopStartResponse = try await webSocket.send(
                action: "start_container",
                data: ["container_id": id],
                timeout: 30
            )

            await refreshContainers()

            // Persist state change
            if let index = containers.firstIndex(where: { $0.id == id }) {
                containers[index].status = "running"
                persistence.saveContainer(containers[index])
            }
        } catch {
            logger.error("Failed to start container: \(error.localizedDescription)")
            errorMessage = "Failed to start container"
        }
    }

    func restartContainer(_ id: String) async {
        isLoading = true
        defer { isLoading = false }

        do {
            let _: StopStartResponse = try await webSocket.send(
                action: "restart_container",
                data: ["container_id": id],
                timeout: 30
            )

            await refreshContainers()

            // Persist state change
            if let index = containers.firstIndex(where: { $0.id == id }) {
                containers[index].status = "running"
                persistence.saveContainer(containers[index])
            }
        } catch {
            logger.error("Failed to restart container: \(error.localizedDescription)")
            errorMessage = "Failed to restart container"
        }
    }

    func clearContainers() {
        containers.removeAll()
        filteredContainers.removeAll()
        persistence.clearContainers()
    }

    // MARK: - Private Methods

    private func observeWebSocket() {
        // Mirror containers from WebSocket client
        containers = webSocket.containers
        applyFilter()
    }

    private func loadFromPersistence() {
        // Load cached containers on startup
        let cachedContainers = persistence.fetchContainers()
        if !cachedContainers.isEmpty {
            containers = cachedContainers
            logger.debug("Loaded \(cachedContainers.count) containers from persistence")
        }
    }

    private func applyFilter() {
        switch selectedStatus {
        case .all:
            filteredContainers = containers
        case .running:
            filteredContainers = containers.filter { $0.status.lowercased() == "running" }
        case .stopped:
            filteredContainers = containers.filter { $0.status.lowercased() == "stopped" || $0.status.lowercased() == "exited" }
        case .paused:
            filteredContainers = containers.filter { $0.status.lowercased() == "paused" }
        }
    }
}
