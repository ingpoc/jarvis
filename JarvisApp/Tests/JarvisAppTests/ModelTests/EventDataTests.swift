import XCTest
@testable import JarvisApp

// MARK: - TimelineEvent Tests

final class TimelineEventTests: XCTestCase {
    // MARK: - Initialization Tests

    func testEventInitialization() {
        let event = TimelineEvent(
            id: "test-123",
            timestamp: 1_700_000_000.0,
            eventType: "tool_use",
            summary: "Test summary",
            sessionId: "session-1",
            taskId: "task-1",
            featureId: "feature-1",
            costUsd: 0.05
        )

        XCTAssertEqual(event.id, "test-123")
        XCTAssertEqual(event.eventType, "tool_use")
        XCTAssertEqual(event.summary, "Test summary")
        XCTAssertEqual(event.sessionId, "session-1")
        XCTAssertEqual(event.taskId, "task-1")
        XCTAssertEqual(event.featureId, "feature-1")
        XCTAssertEqual(event.costUsd ?? 0.0, 0.05, accuracy: 0.001)
    }

    func testEventDate() {
        let event = TimelineEvent(
            id: "test",
            timestamp: 0.0,
            eventType: "test",
            summary: "Test",
            sessionId: nil,
            taskId: nil,
            featureId: nil,
            costUsd: nil
        )

        XCTAssertEqual(event.date.timeIntervalSince1970, 0, accuracy: 1.0)
    }

    func testEventTimeString() {
        let event = TimelineEvent(
            id: "test",
            timestamp: 1_700_000_000.0,
            eventType: "test",
            summary: "Test",
            sessionId: nil,
            taskId: nil,
            featureId: nil,
            costUsd: nil
        )

        // Time should be in HH:mm:ss format
        XCTAssertTrue(event.timeString.contains(":"))
    }

    // MARK: - Codable Tests

    func testEventDecoding() throws {
        let json = """
        {
            "id": "event-1",
            "timestamp": 1700000000.0,
            "event_type": "tool_use",
            "summary": "Using tool: bash",
            "session_id": "session-1",
            "task_id": "task-1",
            "feature_id": "feature-1",
            "cost_usd": 0.05
        }
        """.data(using: .utf8)!

        let decoder = JSONDecoder()
        let event = try XCTUnwrap(try decoder.decode(TimelineEvent.self, from: json))

        XCTAssertEqual(event.id, "event-1")
        XCTAssertEqual(event.eventType, "tool_use")
        XCTAssertEqual(event.summary, "Using tool: bash")
    }

    func testEventDecodingWithGeneratedId() throws {
        let json = """
        {
            "timestamp": 1700000000.0,
            "event_type": "test",
            "summary": "Test event"
        }
        """.data(using: .utf8)!

        let decoder = JSONDecoder()
        let event = try XCTUnwrap(try decoder.decode(TimelineEvent.self, from: json))

        // Should generate ID from timestamp+type
        XCTAssertTrue(event.id == "1700000000.0-test")
    }

    func testEventDecodingWithIntId() throws {
        let json = """
        {
            "id": 123,
            "timestamp": 1700000000.0,
            "event_type": "test",
            "summary": "Test event"
        }
        """.data(using: .utf8)!

        let decoder = JSONDecoder()
        let event = try XCTUnwrap(try decoder.decode(TimelineEvent.self, from: json))

        // Should convert int ID to string
        XCTAssertEqual(event.id, "123")
    }
}
