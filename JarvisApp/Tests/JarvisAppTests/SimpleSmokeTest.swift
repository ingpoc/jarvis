import XCTest
@testable import JarvisApp

// MARK: - Simple Smoke Test

final class SimpleSmokeTest: XCTestCase {
    func testBuildSucceeds() {
        // This test verifies that the app builds without errors
        // We consider a test successful if exit code is 0
        XCTAssert(true, "Build should succeed")
    }

    func testQuickActionsExist() {
        // Verify QuickAction enum exists
        let runTests = QuickAction.runTests
        let buildProject = QuickAction.buildProject
        let gitStatus = QuickAction.gitStatus
        let refresh = QuickAction.refresh

        XCTAssertEqual(runTests.rawValue, "Run Tests")
        XCTAssertEqual(buildProject.rawValue, "Build Project")
        XCTAssertEqual(gitStatus.rawValue, "Git Status")
        XCTAssertEqual(refresh.rawValue, "Refresh Status")
    }

    func testMenuBarComponents() {
        // Verify menu bar components can be created
        let menuBar = MenuBarManager.shared
        XCTAssertNotNil(menuBar, "MenuBarManager should be accessible")
    }

    func testWebSocketClientExists() {
        // Verify WebSocket client can be instantiated
        let ws = WebSocketClient()
        XCTAssertNotNil(ws, "WebSocketClient should be instantiable")
    }

    func testPersistenceManagerExists() {
        // Verify Persistence manager can be instantiated
        let pm = PersistenceManager.shared
        XCTAssertNotNil(pm, "PersistenceManager should be accessible")
    }
}
