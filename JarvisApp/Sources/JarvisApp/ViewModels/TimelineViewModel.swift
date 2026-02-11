import Foundation
import Observation
import OSLog

// MARK: - Timeline ViewModel

@Observable
@MainActor
final class TimelineViewModel {
    // MARK: - Dependencies

    private let webSocket: WebSocketClientProtocol
    private let persistence: PersistenceManager
    private let logger = Logger(subsystem: "com.jarvis.app", category: "TimelineViewModel")

    // MARK: - Output

    var events: [TimelineEvent] = []
    var filteredEvents: [TimelineEvent] = []
    var selectedEventType: EventTypeFilter = .all
    var isLoading = false
    var errorMessage: String?

    private let maxEvents = 200

    // MARK: - Initialization

    init(webSocket: WebSocketClientProtocol, persistence: PersistenceManager = .shared) {
        self.webSocket = webSocket
        self.persistence = persistence
        observeWebSocket()
        loadFromPersistence()
    }

    // MARK: - Public API

    func refreshEvents() async {
        isLoading = true
        defer { isLoading = false }

        do {
            // Load from WebSocket (for latest events)
            let wsEvents = Array(webSocket.events.prefix(maxEvents))
            events = wsEvents

            // Persist to disk
            for event in wsEvents {
                persistence.saveEvent(event)
            }

            applyFilter()
            errorMessage = nil
        } catch {
            logger.error("Failed to refresh events: \(error.localizedDescription)")
            errorMessage = "Failed to refresh events"
        }
    }

    func clearEvents() {
        events.removeAll()
        filteredEvents.removeAll()
        persistence.clearEvents()
    }

    func filterEvents(_ type: EventTypeFilter) {
        selectedEventType = type
        applyFilter()
    }

    func exportEvents() -> String {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]

        do {
            let data = try encoder.encode(filteredEvents)
            return String(data: data, encoding: .utf8) ?? "{}"
        } catch {
            logger.error("Failed to encode events: \(error.localizedDescription)")
            return "[]"
        }
    }

    // MARK: - Private Methods

    private func observeWebSocket() {
        // Mirror events from WebSocket client
        events = Array(webSocket.events.prefix(maxEvents))
        applyFilter()
    }

    private func loadFromPersistence() {
        // Load cached events on startup
        let cachedEvents = persistence.fetchEvents()
        if !cachedEvents.isEmpty {
            events = cachedEvents
        }
    }

    private func applyFilter() {
        switch selectedEventType {
        case .all:
            filteredEvents = events
        case .approval:
            filteredEvents = events.filter { $0.eventType == "approval_needed" }
        case .command:
            filteredEvents = events.filter { $0.eventType == "command_executed" }
        case .error:
            filteredEvents = events.filter { $0.eventType == "error" }
        }
    }

    private func syncEvents(with wsEvents: [TimelineEvent]) {
        // Merge cached events with latest WebSocket events
        let cachedEvents = persistence.fetchEvents()

        // Create a map of existing events by ID
        var eventMap: [String: TimelineEvent] = [:]
        for event in cachedEvents {
            eventMap[event.id] = event
        }

        // Update with latest events from WebSocket
        for event in wsEvents {
            eventMap[event.id] = event
        }

        // Convert back to array and sort by timestamp
        let sortedEvents = Array(eventMap.values)
            .sorted { $0.timestamp > $1.timestamp }

        // Take only maxEvents
        events = Array(sortedEvents.prefix(maxEvents))
    }
}

// MARK: - Event Type Filter

enum EventTypeFilter: String, CaseIterable {
    case all
    case approval
    case command
    case error

    var displayName: String {
        switch self {
        case .all: "All Events"
        case .approval: "Approvals Only"
        case .command: "Commands Only"
        case .error: "Errors Only"
        }
    }
}
