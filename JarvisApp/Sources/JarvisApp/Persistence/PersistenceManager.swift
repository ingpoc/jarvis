import Foundation
import Observation
import OSLog

// MARK: - Codable Event Wrapper

struct EventData: Codable {
    let id: String
    let timestamp: Double
    let eventType: String
    let summary: String
    let sessionId: String?
    let taskId: String?
    let featureId: String?
    let costUsd: Double?

    private enum CodingKeys: String, CodingKey {
        case id, timestamp, summary
        case eventType = "event_type"
        case sessionId = "session_id"
        case taskId = "task_id"
        case featureId = "feature_id"
        case costUsd = "cost_usd"
    }
}

struct ContainerData: Codable {
    let id: String
    let name: String
    let status: String
    let image: String
    let cpus: Int?
    let memory: String?
    let taskId: String?
}

// MARK: - Persistence Manager

@MainActor
@Observable
final class PersistenceManager {
    static let shared = PersistenceManager()

    private let logger = Logger(subsystem: "com.jarvis.app", category: "Persistence")

    // MARK: - State

    var events: [EventData] = []
    var containers: [ContainerData] = []

    // MARK: - Public API

    func initialize() {
        loadFromDisk()
    }

    // MARK: - Event Persistence

    // MARK: - Event Persistence

    func saveEvent(_ event: TimelineEvent) {
        let eventData = EventData(
            id: event.id,
            timestamp: event.timestamp,
            eventType: event.eventType,
            summary: event.summary,
            sessionId: event.sessionId,
            taskId: event.taskId,
            featureId: event.featureId,
            costUsd: event.costUsd
        )
        events.append(eventData)
        saveToDisk()
        logger.debug("Saved event: \(event.id)")
    }

    func saveEvents(_ newEvents: [TimelineEvent]) {
        events = newEvents.map { event in
            EventData(
                id: event.id,
                timestamp: event.timestamp,
                eventType: event.eventType,
                summary: event.summary,
                sessionId: event.sessionId,
                taskId: event.taskId,
                featureId: event.featureId,
                costUsd: event.costUsd
            )
        }
        saveToDisk()
        logger.debug("Saved \(self.events.count) events")
    }

    func fetchEvents() -> [TimelineEvent] {
        loadFromDiskIfNeeded()
        return events.map { eventData in
            TimelineEvent(
                id: eventData.id,
                timestamp: eventData.timestamp,
                eventType: eventData.eventType,
                summary: eventData.summary,
                sessionId: eventData.sessionId,
                taskId: eventData.taskId,
                featureId: eventData.featureId,
                costUsd: eventData.costUsd
            )
        }
    }

    // MARK: - Container Persistence

    func saveContainers(_ newContainers: [ContainerInfo]) {
        containers = newContainers.map { container in
            ContainerData(
                id: container.id,
                name: container.name,
                status: container.status,
                image: container.image,
                cpus: container.cpus,
                memory: container.memory,
                taskId: container.taskId
            )
        }
        saveToDisk()
        logger.debug("Saved \(self.containers.count) containers")
    }

    func saveContainer(_ container: ContainerInfo) {
        // Update or add single container
        if let index = containers.firstIndex(where: { $0.id == container.id }) {
            containers[index] = ContainerData(
                id: container.id,
                name: container.name,
                status: container.status,
                image: container.image,
                cpus: container.cpus,
                memory: container.memory,
                taskId: container.taskId
            )
        } else {
            containers.append(ContainerData(
                id: container.id,
                name: container.name,
                status: container.status,
                image: container.image,
                cpus: container.cpus,
                memory: container.memory,
                taskId: container.taskId
            ))
        }
        saveToDisk()
        logger.debug("Saved container: \(container.name)")
    }

    func fetchContainers() -> [ContainerInfo] {
        loadFromDiskIfNeeded()
        return containers.map { containerData in
            ContainerInfo(
                id: containerData.id,
                name: containerData.name,
                status: containerData.status,
                image: containerData.image,
                cpus: containerData.cpus,
                memory: containerData.memory,
                taskId: containerData.taskId
            )
        }
    }

    func clearContainers() {
        containers.removeAll()
        UserDefaults.standard.removeObject(forKey: "cached_containers")
        logger.debug("Cleared all containers")
    }

    func clearEvents() {
        events.removeAll()
        UserDefaults.standard.removeObject(forKey: "cached_events")
        logger.debug("Cleared all events")
    }

    // MARK: - Data Export

    func exportEventsAsJSON() -> String {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        encoder.dateEncodingStrategy = .secondsSince1970

        do {
            let data = try encoder.encode(fetchEvents())
            return String(data: data, encoding: .utf8) ?? "[]"
        } catch {
            logger.error("Failed to export: \(error.localizedDescription)")
            return "[]"
        }
    }

    // MARK: - Sync

    func syncWithWebSocket(_ webSocket: any WebSocketClientProtocol) async {
        // Save events
        let eventsToSave = Array(webSocket.events.prefix(200))
        saveEvents(eventsToSave)

        // Save containers
        saveContainers(webSocket.containers)
    }

    // MARK: - Private Methods

    private func loadFromDiskIfNeeded() {
        guard !events.isEmpty && !containers.isEmpty else { return }
        loadFromDisk()
    }

    private func loadFromDisk() {
        if let data = UserDefaults.standard.data(forKey: "cached_events"),
           let decoded = try? JSONDecoder().decode([EventData].self, from: data) {
            events = decoded
        }

        if let data = UserDefaults.standard.data(forKey: "cached_containers"),
           let decoded = try? JSONDecoder().decode([ContainerData].self, from: data) {
            containers = decoded
        }
    }

    private func saveToDisk() {
        if let data = try? JSONEncoder().encode(events) {
            UserDefaults.standard.set(data, forKey: "cached_events")
        }

        if let data = try? JSONEncoder().encode(containers) {
            UserDefaults.standard.set(data, forKey: "cached_containers")
        }
    }
}
