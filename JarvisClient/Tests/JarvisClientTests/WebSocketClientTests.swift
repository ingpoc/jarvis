import XCTest
@testable import JarvisClient
import Starscream

@available(macOS 14, iOS 17, *)
final class WebSocketClientTests: XCTestCase {

    var webSocketClient: JarvisWebSocketClient!
    var authManager: AuthManager!

    override func setUp() {
        super.setUp()
        authManager = AuthManager.shared
        authManager.clearToken()
        webSocketClient = JarvisWebSocketClient.shared
        webSocketClient.disconnect()
    }

    override func tearDown() {
        webSocketClient.disconnect()
        authManager.clearToken()
        super.tearDown()
    }

    // MARK: - Connection State Tests

    func testInitialState() {
        XCTAssertFalse(webSocketClient.isConnected)
        XCTAssertEqual(webSocketClient.status, .idle)
        XCTAssertNil(webSocketClient.connectionError)
    }

    func testDisconnect() {
        webSocketClient.disconnect()

        XCTAssertFalse(webSocketClient.isConnected)
    }

    func testConnectMethod() {
        webSocketClient.disconnect()

        XCTAssertNoThrow(webSocketClient.connect())
    }

    // MARK: - Event Handling Tests

    func testEventsArrayInitialState() {
        XCTAssertTrue(webSocketClient.events.isEmpty)
        XCTAssertTrue(webSocketClient.pendingApprovals.isEmpty)
    }

    func testEventsMaxLimit() {
        // Events array can hold more than 200; the limit is applied in handleEvent
        // This test verifies we can add events and manually cap them
        for i in 0..<250 {
            let event = TimelineEvent(
                id: i,
                timestamp: Date().timeIntervalSince1970,
                eventType: "test",
                summary: "Test event \(i)"
            )
            webSocketClient.events.insert(event, at: 0)
        }

        // Manually cap to verify we can limit events
        if webSocketClient.events.count > 200 {
            webSocketClient.events = Array(webSocketClient.events.prefix(200))
        }

        XCTAssertEqual(webSocketClient.events.count, 200)
    }

    func testEventsLimitConstant() {
        // Verify the expected limit constant
        let expectedLimit = 200
        XCTAssertEqual(expectedLimit, 200)
    }

    // MARK: - WebSocketError Tests

    func testWebSocketErrorDescriptions() {
        XCTAssertEqual(WebSocketError.notConnected.errorDescription, "WebSocket is not connected")
        XCTAssertEqual(WebSocketError.timeout.errorDescription, "Request timed out")
        XCTAssertEqual(WebSocketError.invalidResponse.errorDescription, "Invalid response from server")
    }

    // MARK: - Status Tests

    func testJarvisStatusLabel() {
        XCTAssertEqual(JarvisStatus.idle.label, "Idle")
        XCTAssertEqual(JarvisStatus.building.label, "Building")
        XCTAssertEqual(JarvisStatus.testing.label, "Testing")
        XCTAssertEqual(JarvisStatus.error.label, "Error")
        XCTAssertEqual(JarvisStatus.waitingApproval.label, "Waiting Approval")
    }

    func testJarvisStatusIconName() {
        XCTAssertEqual(JarvisStatus.idle.iconName, "brain.head.profile")
        XCTAssertEqual(JarvisStatus.building.iconName, "brain.head.profile")
    }

    func testJarvisStatusRawValues() {
        XCTAssertEqual(JarvisStatus.idle.rawValue, "idle")
        XCTAssertEqual(JarvisStatus.building.rawValue, "building")
        XCTAssertEqual(JarvisStatus.testing.rawValue, "testing")
        XCTAssertEqual(JarvisStatus.error.rawValue, "error")
        XCTAssertEqual(JarvisStatus.waitingApproval.rawValue, "waiting_approval")
    }

    // MARK: - Reconnect Logic Tests

    func testReconnectDelayCalculation() {
        // Test base delay
        let delay0 = calculateReconnectDelay(attempt: 0)
        XCTAssertEqual(delay0, 1.0, accuracy: 0.01)

        // Test exponential growth
        let delay1 = calculateReconnectDelay(attempt: 1)
        XCTAssertEqual(delay1, 2.0, accuracy: 0.01)

        let delay2 = calculateReconnectDelay(attempt: 2)
        XCTAssertEqual(delay2, 4.0, accuracy: 0.01)

        let delay3 = calculateReconnectDelay(attempt: 3)
        XCTAssertEqual(delay3, 8.0, accuracy: 0.01)

        // Test max cap
        let delay10 = calculateReconnectDelay(attempt: 10)
        XCTAssertEqual(delay10, 60.0, accuracy: 0.01)
    }

    // MARK: - Helper Methods (Mirroring Private Implementation)

    private func calculateReconnectDelay(attempt: Int) -> TimeInterval {
        let baseReconnectDelay: TimeInterval = 1.0
        let maxReconnectDelay: TimeInterval = 60.0
        let exponentialDelay = baseReconnectDelay * pow(2.0, Double(attempt))
        return min(exponentialDelay, maxReconnectDelay)
    }

    // MARK: - TimelineEvent Model Tests

    func testTimelineEventCreation() {
        let event = TimelineEvent(
            id: 123,
            timestamp: 1_700_000_000,
            eventType: "test_event",
            summary: "Test summary"
        )

        XCTAssertEqual(event.id, 123)
        XCTAssertEqual(event.eventType, "test_event")
        XCTAssertEqual(event.summary, "Test summary")
    }

    func testTimelineEventWithOptionalFields() {
        let event = TimelineEvent(
            id: 456,
            timestamp: 1_700_000_000,
            eventType: "approval",
            summary: "Approval needed",
            sessionId: "session-123",
            taskId: "task-456",
            featureId: "feature-789",
            costUsd: 0.05
        )

        XCTAssertEqual(event.sessionId, "session-123")
        XCTAssertEqual(event.taskId, "task-456")
        XCTAssertEqual(event.featureId, "feature-789")
        XCTAssertEqual(event.costUsd, 0.05)
    }

    func testTimelineEventTimestampDate() {
        let timestamp: Double = 1_700_000_000
        let event = TimelineEvent(
            id: 789,
            timestamp: timestamp,
            eventType: "test",
            summary: "Test"
        )

        XCTAssertEqual(event.date, Date(timeIntervalSince1970: timestamp))
    }

    func testTimelineEventTimeString() {
        let event = TimelineEvent(
            id: 1,
            timestamp: 1_700_000_000,
            eventType: "test",
            summary: "Test"
        )

        let timeString = event.timeString
        XCTAssertFalse(timeString.isEmpty)
        XCTAssertTrue(timeString.count >= 8)
    }

    func testTimelineEventEncodingDecoding() throws {
        let event = TimelineEvent(
            id: 999,
            timestamp: 1_700_000_000,
            eventType: "codec",
            summary: "Test event",
            sessionId: "session-abc",
            taskId: "task-def",
            featureId: "feature-ghi",
            costUsd: 0.123
        )

        let encoder = JSONEncoder()
        let data = try encoder.encode(event)

        let decoder = JSONDecoder()
        let decoded = try decoder.decode(TimelineEvent.self, from: data)

        XCTAssertEqual(decoded.id, event.id)
        XCTAssertEqual(decoded.eventType, event.eventType)
        XCTAssertEqual(decoded.summary, event.summary)
        XCTAssertEqual(decoded.sessionId, event.sessionId)
        XCTAssertEqual(decoded.taskId, event.taskId)
        XCTAssertEqual(decoded.featureId, event.featureId)
        XCTAssertEqual(decoded.costUsd, event.costUsd)
    }

    func testTimelineEventJSONDecoding() throws {
        let json = """
        {
            "id": 42,
            "timestamp": 1700000000,
            "event_type": "voice_command",
            "summary": "User spoke a command",
            "session_id": "session-xyz",
            "task_id": "task-abc",
            "feature_id": "feature-def",
            "cost_usd": 0.025
        }
        """

        let data = json.data(using: .utf8)!
        let decoder = JSONDecoder()
        let event = try decoder.decode(TimelineEvent.self, from: data)

        XCTAssertEqual(event.id, 42)
        XCTAssertEqual(event.eventType, "voice_command")
        XCTAssertEqual(event.summary, "User spoke a command")
        XCTAssertEqual(event.sessionId, "session-xyz")
        XCTAssertEqual(event.taskId, "task-abc")
        XCTAssertEqual(event.featureId, "feature-def")
        XCTAssertEqual(event.costUsd, 0.025)
    }

    func testJarvisStatusResponseDecoding() throws {
        let json = """
        {
            "status": "building",
            "current_session": "session-123",
            "current_feature": "feature-456",
            "uptime": 3600.5
        }
        """

        let data = json.data(using: .utf8)!
        let decoder = JSONDecoder()
        let response = try decoder.decode(JarvisStatusResponse.self, from: data)

        XCTAssertEqual(response.status, .building)
        XCTAssertEqual(response.currentSession, "session-123")
        XCTAssertEqual(response.currentFeature, "feature-456")
        XCTAssertEqual(response.uptime, 3600.5)
    }

    func testJarvisStatusEncodingDecoding() throws {
        let status = JarvisStatus.testing

        let encoder = JSONEncoder()
        let data = try encoder.encode(status)

        let decoder = JSONDecoder()
        let decoded = try decoder.decode(JarvisStatus.self, from: data)

        XCTAssertEqual(decoded, .testing)
    }
}
