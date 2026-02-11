import Foundation
import CoreSpotlight
import UniformTypeIdentifiers
import OSLog

// MARK: - Spotlight Service

@MainActor
@Observable
final class SpotlightService {
    static let shared = SpotlightService()

    private let logger = Logger(subsystem: "com.jarvis.app", category: "Spotlight")
    private let domainIdentifier = "com.jarvis.commands"

    // Maximum number of items to keep in Spotlight index
    private let maxIndexedItems = 50

    private init() {
        logger.info("SpotlightService initialized")
    }

    // MARK: - Public API

    /// Index a timeline event for Spotlight search
    func indexEvent(_ event: TimelineEvent) {
        let attributeSet = CSSearchableItemAttributeSet(itemContentType: UTType.text.identifier)

        attributeSet.title = eventSummary(for: event)
        attributeSet.contentDescription = event.summary
        attributeSet.keywords = keywords(for: event)

        // Add additional metadata
        attributeSet.thumbnailData = thumbnailData(for: event)

        let item = CSSearchableItem(
            uniqueIdentifier: event.id,
            domainIdentifier: domainIdentifier,
            attributeSet: attributeSet
        )

        CSSearchableIndex.default().indexSearchableItems([item]) { error in
            if let error = error {
                self.logger.error("Failed to index event \(event.id): \(error.localizedDescription)")
            } else {
                self.logger.debug("Indexed event: \(event.id)")
            }
        }
    }

    /// Index multiple events (batch operation)
    func indexEvents(_ events: [TimelineEvent]) {
        guard !events.isEmpty else { return }

        let items = events.map { event -> CSSearchableItem in
            let attributeSet = CSSearchableItemAttributeSet(itemContentType: UTType.text.identifier)
            attributeSet.title = eventSummary(for: event)
            attributeSet.contentDescription = event.summary
            attributeSet.keywords = keywords(for: event)
            attributeSet.thumbnailData = thumbnailData(for: event)

            return CSSearchableItem(
                uniqueIdentifier: event.id,
                domainIdentifier: domainIdentifier,
                attributeSet: attributeSet
            )
        }

        CSSearchableIndex.default().indexSearchableItems(items) { error in
            if let error = error {
                self.logger.error("Failed to index batch of \(events.count) events: \(error.localizedDescription)")
            } else {
                self.logger.info("Indexed batch of \(events.count) events")
            }
        }
    }

    /// Index a container for quick actions
    func indexContainer(_ container: ContainerInfo) {
        let attributeSet = CSSearchableItemAttributeSet(itemContentType: UTType.text.identifier)

        attributeSet.title = "Container: \(container.name)"
        attributeSet.contentDescription = "Status: \(container.status) | Image: \(container.image)"
        attributeSet.keywords = ["container", container.name, container.status, "docker"]

        // Add action keywords
        if container.status == "running" {
            attributeSet.keywords?.append(contentsOf: ["stop", "pause", "logs"])
        } else {
            attributeSet.keywords?.append(contentsOf: ["start", "run"])
        }

        let item = CSSearchableItem(
            uniqueIdentifier: "container-\(container.id)",
            domainIdentifier: "\(domainIdentifier).containers",
            attributeSet: attributeSet
        )

        CSSearchableIndex.default().indexSearchableItems([item]) { error in
            if let error = error {
                self.logger.error("Failed to index container \(container.id): \(error.localizedDescription)")
            }
        }
    }

    /// Index a quick action/command
    func indexCommand(id: String, title: String, description: String, keywords: [String] = []) {
        let attributeSet = CSSearchableItemAttributeSet(itemContentType: UTType.text.identifier)

        attributeSet.title = title
        attributeSet.contentDescription = description
        attributeSet.keywords = keywords + ["jarvis", "command", "action"]

        let item = CSSearchableItem(
            uniqueIdentifier: id,
            domainIdentifier: "\(domainIdentifier).commands",
            attributeSet: attributeSet
        )

        CSSearchableIndex.default().indexSearchableItems([item]) { error in
            if let error = error {
                self.logger.error("Failed to index command \(id): \(error.localizedDescription)")
            }
        }
    }

    /// Remove an item from the index
    func removeItem(withIdentifier identifier: String) {
        CSSearchableIndex.default().deleteSearchableItems(withIdentifiers: [identifier]) { error in
            if let error = error {
                self.logger.error("Failed to remove item \(identifier): \(error.localizedDescription)")
            }
        }
    }

    /// Remove all items from a domain
    func removeItems(domainIdentifier: String) {
        CSSearchableIndex.default().deleteSearchableItems(withDomainIdentifiers: [domainIdentifier]) { error in
            if let error = error {
                self.logger.error("Failed to clear domain \(domainIdentifier): \(error.localizedDescription)")
            }
        }
    }

    /// Clear all Jarvis items from Spotlight
    func clearAllItems() {
        CSSearchableIndex.default().deleteSearchableItems(withDomainIdentifiers: [
            domainIdentifier,
            "\(domainIdentifier).containers",
            "\(domainIdentifier).commands",
            "\(domainIdentifier).approvals"
        ]) { error in
            if let error = error {
                self.logger.error("Failed to clear all items: \(error.localizedDescription)")
            } else {
                self.logger.info("Cleared all Spotlight items")
            }
        }
    }

    // MARK: - Private Helpers

    private func eventSummary(for event: TimelineEvent) -> String {
        switch event.eventType {
        case "tool_use":
            return "Tool: \(toolName(from: event.summary))"
        case "approval_needed":
            return "Approval Required"
        case "error", "failure":
            return "Error: \(eventType(from: event.summary))"
        case "success", "complete":
            return "Completed: \(eventType(from: event.summary))"
        case "build_start":
            return "Build Started"
        case "build_end":
            return "Build Finished"
        case "test_start":
            return "Tests Started"
        case "test_end":
            return "Tests Finished"
        default:
            return event.eventType.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }

    private func keywords(for event: TimelineEvent) -> [String] {
        var keywords = ["jarvis", "event", event.eventType]

        switch event.eventType {
        case "tool_use":
            let tool = toolName(from: event.summary)
            keywords.append(contentsOf: ["tool", tool, "execute"])
        case "approval_needed":
            keywords.append(contentsOf: ["approve", "permission", "confirm"])
        case "error", "failure":
            keywords.append(contentsOf: ["error", "failed", "issue", "problem"])
        case "test_start", "test_end":
            keywords.append(contentsOf: ["test", "testing", "verify"])
        case "build_start", "build_end":
            keywords.append(contentsOf: ["build", "compile"])
        default:
            break
        }

        if let taskId = event.taskId {
            keywords.append(taskId)
        }
        if let sessionId = event.sessionId {
            keywords.append(sessionId)
        }

        return keywords
    }

    private func toolName(from summary: String) -> String {
        // Extract tool name from summary like "Using tool: bash" or "Tool: git_clone"
        if let range = summary.range(of: "tool:\\s*", options: .regularExpression) {
            let after = summary[range.upperBound...]
            return after.components(separatedBy: .whitespacesAndNewlines).first ?? "tool"
        }
        return "tool"
    }

    private func eventType(from summary: String) -> String {
        // Extract event type from summary
        return summary.components(separatedBy: ":").first ?? "event"
    }

    private func thumbnailData(for event: TimelineEvent) -> Data? {
        // Generate a simple icon based on event type
        // In a full implementation, you'd return actual SF Symbol image data
        return nil
    }
}

// MARK: - Spotlight Action Handler

extension SpotlightService {
    /// Handle a Spotlight search item selection
    func handleSelectedItem(identifier: String, webSocket: WebSocketClientProtocol) async -> Bool {
        logger.info("Spotlight item selected: \(identifier)")

        // Parse the identifier to determine action
        if identifier.hasPrefix("container-") {
            // Container action: container-{id}
            let containerId = String(identifier.dropFirst(10))
            return await handleContainerAction(id: containerId, webSocket: webSocket)
        } else if identifier == "command-refresh" {
            // Quick action: refresh status
            return await handleRefreshAction(webSocket: webSocket)
        } else if identifier == "command-approvals" {
            // Quick action: show approvals
            return await handleApprovalsAction(webSocket: webSocket)
        } else if identifier == "command-containers" {
            // Quick action: show containers
            return await handleContainersAction(webSocket: webSocket)
        } else {
            // Timeline event: show event details
            return await handleEventAction(eventId: identifier, webSocket: webSocket)
        }
    }

    private func handleContainerAction(id: String, webSocket: WebSocketClientProtocol) async -> Bool {
        // Find the container and show its details
        // For now, just refresh containers
        do {
            let _: ContainersResponse = try await webSocket.send(
                action: "get_containers",
                data: nil,
                timeout: 10
            )
            return true
        } catch {
            logger.error("Failed to get containers for Spotlight action: \(error)")
            return false
        }
    }

    private func handleRefreshAction(webSocket: WebSocketClientProtocol) async -> Bool {
        do {
            let _: JarvisStatusResponse = try await webSocket.send(
                action: "get_status",
                data: nil,
                timeout: 10
            )
            return true
        } catch {
            logger.error("Failed to refresh for Spotlight action: \(error)")
            return false
        }
    }

    private func handleApprovalsAction(webSocket: WebSocketClientProtocol) async -> Bool {
        // Trigger a request to get pending approvals
        // This would typically show the approvals view
        return true
    }

    private func handleContainersAction(webSocket: WebSocketClientProtocol) async -> Bool {
        do {
            let _: ContainersResponse = try await webSocket.send(
                action: "get_containers",
                data: nil,
                timeout: 10
            )
            return true
        } catch {
            logger.error("Failed to get containers for Spotlight action: \(error)")
            return false
        }
    }

    private func handleEventAction(eventId: String, webSocket: WebSocketClientProtocol) async -> Bool {
        // Find and display the event in the timeline
        // This would typically navigate to the timeline and highlight the event
        logger.info("Requested to show event: \(eventId)")
        return true
    }
}

// MARK: - Spotlight Indexable Commands

extension SpotlightService {
    /// Index common quick actions for Jarvis
    func indexQuickActions() {
        let quickActions: [(id: String, title: String, description: String, keywords: [String])] = [
            (
                "command-refresh",
                "Refresh Jarvis Status",
                "Get the current status of Jarvis daemon",
                ["refresh", "status", "update"]
            ),
            (
                "command-containers",
                "Show Containers",
                "View all Docker containers managed by Jarvis",
                ["containers", "docker", "list"]
            ),
            (
                "command-approvals",
                "Pending Approvals",
                "View actions waiting for your approval",
                ["approval", "approve", "pending"]
            ),
            (
                "command-timeline",
                "Event Timeline",
                "View recent events and activities",
                ["timeline", "events", "history", "log"]
            )
        ]

        for action in quickActions {
            indexCommand(
                id: action.id,
                title: action.title,
                description: action.description,
                keywords: action.keywords
            )
        }
    }
}
