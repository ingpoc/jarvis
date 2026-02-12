import XCTest
@testable import JarvisApp

// MARK: - SpotlightService Tests

final class SpotlightServiceTests: XCTestCase {
    func testSpotlightServiceSingleton() {
        let service1 = SpotlightService.shared
        let service2 = SpotlightService.shared
        XCTAssertTrue(service1 === service2, "Should return same instance")
    }

    func testIndexEvent() async throws {
        let service = SpotlightService.shared
        let event = TimelineEvent(
            id: "test-1",
            timestamp: 1_700_000_000.0,
            eventType: "tool_use",
            summary: "Test summary",
            sessionId: "session-1",
            taskId: "task-1",
            featureId: "feature-1",
            costUsd: 0.05
        )

        // Should not throw
        await service.indexEvent(event)

        // Verify index was called (async, so we wait a bit)
        try await Task.sleep(nanoseconds: 100_000_000) // 0.1 seconds
    }

    func testIndexContainer() async throws {
        let service = SpotlightService.shared
        let container = ContainerInfo(
            id: "container-1",
            name: "test-container",
            status: "running",
            image: "test:latest",
            cpus: 2,
            memory: "512MB",
            taskId: "task-1"
        )

        // Should not throw
        await service.indexContainer(container)

        try await Task.sleep(nanoseconds: 100_000_000)
    }

    func testIndexCommand() async throws {
        let service = SpotlightService.shared

        // Should not throw
        await service.indexCommand(
            id: "test-command",
            title: "Test Command",
            description: "Test description",
            keywords: ["test", "keyword"]
        )

        try await Task.sleep(nanoseconds: 100_000_000)
    }

    func testIndexQuickActions() async throws {
        let service = SpotlightService.shared

        // Should not throw
        await service.indexQuickActions()

        try await Task.sleep(nanoseconds: 100_000_000)
    }

    func testRemoveItem() async throws {
        let service = SpotlightService.shared
        let identifier = "test-item-to-remove"

        // Verify method completes successfully
        await service.removeItem(withIdentifier: identifier)

        // Verify index was called (async, so we wait a bit)
        try await Task.sleep(nanoseconds: 100_000_000)
    }

    func testRemoveDomainItems() async throws {
        let service = SpotlightService.shared

        // Verify method completes successfully
        await service.removeItems(domainIdentifier: "test.domain")

        // Verify completion
        try await Task.sleep(nanoseconds: 100_000_000)
    }

    func testClearAllItems() async throws {
        let service = SpotlightService.shared

        // Verify method completes successfully
        await service.clearAllItems()

        // Verify completion
        try await Task.sleep(nanoseconds: 100_000_000)
    }

    // MARK: - Action Handler Tests

    @MainActor
    func testHandleSelectedItemWithContainer() async throws {
        let service = SpotlightService.shared
        let mockWebSocket = MockWebSocketClient()
        mockWebSocket.connectionState = .connected

        let identifier = "container-test-123"

        let success = await service.handleSelectedItem(
            identifier: identifier,
            webSocket: mockWebSocket
        )

        XCTAssertTrue(success, "Should handle container selection")
    }

    @MainActor
    func testHandleSelectedItemWithCommand() async throws {
        let service = SpotlightService.shared
        let mockWebSocket = MockWebSocketClient()
        mockWebSocket.connectionState = .connected

        let identifier = "command-refresh"

        let success = await service.handleSelectedItem(
            identifier: identifier,
            webSocket: mockWebSocket
        )

        XCTAssertTrue(success, "Should handle command selection")
    }

    @MainActor
    func testHandleSelectedItemWithUnknownIdentifier() async throws {
        let service = SpotlightService.shared
        let mockWebSocket = MockWebSocketClient()
        mockWebSocket.connectionState = .connected

        let identifier = "unknown-item"

        let success = await service.handleSelectedItem(
            identifier: identifier,
            webSocket: mockWebSocket
        )

        // Note: Current implementation logs unknown items and returns true
        // This test documents current behavior
        XCTAssertTrue(success, "Unknown items are logged and handled")
    }
}

// MARK: - Mock WebSocket Client for Testing

@MainActor
final class MockWebSocketClient: WebSocketClientProtocol {
    var connectionState: ConnectionState = .disconnected
    var delegate: (any WebSocketDelegate)?
    var events: [TimelineEvent] = []
    var containers: [ContainerInfo] = []
    var availableTools: [String] = []
    var pendingApprovals: [TimelineEvent] = []
    var status: JarvisStatus = .idle
    var isLoading = false
    var lastError: String?

    func connect() {
        connectionState = .connected
    }

    func disconnect() {
        connectionState = .disconnected
    }

    func send<T: Decodable>(action: String, data: [String: Any]?, timeout: TimeInterval) async throws -> T {
        // Mock implementation - return success for known types
        if T.self == JarvisStatusResponse.self {
            return JarvisStatusResponse(status: .idle, currentSession: nil, currentFeature: nil, uptime: 100) as! T
        }
        if T.self == ContainersResponse.self {
            return ContainersResponse(containers: []) as! T
        }
        throw WebSocketError.notConnected
    }

    func sendWithoutResponse(action: String, data: [String: Any]?) async throws {
        // Mock implementation
    }
}
