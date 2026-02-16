import XCTest
@testable import JarvisApp
import SwiftUI

// MARK: - View Extension Tests

final class ViewExtensionsTests: XCTestCase {
    func testStatusBadgeIdle() {
        let status = JarvisStatus.idle
        XCTAssertEqual(status.iconName, "brain.head.profile")
        XCTAssertEqual(status.label, "Idle")
    }

    func testStatusBadgeBuilding() {
        let status = JarvisStatus.building
        XCTAssertEqual(status.label, "Building")
    }

    func testStatusBadgeTesting() {
        let status = JarvisStatus.testing
        XCTAssertEqual(status.label, "Testing")
    }

    func testStatusBadgeError() {
        let status = JarvisStatus.error
        XCTAssertEqual(status.label, "Error")
    }

    func testStatusBadgeWaitingApproval() {
        let status = JarvisStatus.waitingApproval
        XCTAssertEqual(status.label, "Waiting Approval")
    }
}

// MARK: - Design System Tests

final class DesignSystemTests: XCTestCase {
    func testSpacingConstants() {
        XCTAssertEqual(DesignSystem.Spacing.xs, 4)
        XCTAssertEqual(DesignSystem.Spacing.sm, 8)
        XCTAssertEqual(DesignSystem.Spacing.md, 12)
        XCTAssertEqual(DesignSystem.Spacing.lg, 16)
        XCTAssertEqual(DesignSystem.Spacing.xl, 24)
    }

    func testColorConstants() {
        // Verify status colors exist
        XCTAssertNotNil(DesignSystem.Colors.statusRunning)
        XCTAssertNotNil(DesignSystem.Colors.statusStopped)
        XCTAssertNotNil(DesignSystem.Colors.statusPaused)
        XCTAssertNotNil(DesignSystem.Colors.statusError)
    }
}

// MARK: - Event Colors Tests

final class EventColorsTests: XCTestCase {
    func testColorForEventType() {
        XCTAssertEqual(
            EventColors.color(for: "tool_use"),
            .blue
        )
        XCTAssertEqual(
            EventColors.color(for: "approval_needed"),
            .orange
        )
        XCTAssertEqual(
            EventColors.color(for: "error"),
            .red
        )
        XCTAssertEqual(
            EventColors.color(for: "success"),
            .green
        )
    }

    func testColorForUnknownEventType() {
        let color = EventColors.color(for: "unknown_event")
        XCTAssertEqual(color, .primary)
    }
}
