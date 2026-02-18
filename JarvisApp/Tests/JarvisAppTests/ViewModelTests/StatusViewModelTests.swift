import XCTest
@testable import JarvisApp

// MARK: - StatusViewModel Tests

final class StatusViewModelTests: XCTestCase {
    @MainActor
    func testStatusViewModelInitialization() {
        let mockWebSocket = MockWebSocketClient()
        let viewModel = StatusViewModel(webSocket: mockWebSocket)

        XCTAssertNotNil(viewModel)
    }

    @MainActor
    func testRefreshStatusWhenConnected() async throws {
        let mockWebSocket = MockWebSocketClient()
        mockWebSocket.connectionState = .connected

        let viewModel = StatusViewModel(webSocket: mockWebSocket)

        try await viewModel.refreshStatus()

        XCTAssertEqual(viewModel.isConnected, true)
        XCTAssertNil(viewModel.errorMessage)
    }

    @MainActor
    func testRefreshStatusWhenDisconnected() async throws {
        let mockWebSocket = MockWebSocketClient()
        mockWebSocket.connectionState = .disconnected

        let viewModel = StatusViewModel(webSocket: mockWebSocket)

        try await viewModel.refreshStatus()

        XCTAssertEqual(viewModel.isConnected, false)
        XCTAssertNotNil(viewModel.errorMessage)
    }
}
