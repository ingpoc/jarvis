import XCTest
@testable import JarvisClient

@available(macOS 14, iOS 17, *)
final class AuthManagerTests: XCTestCase {

    var authManager: AuthManager!

    override func setUp() {
        super.setUp()
        authManager = AuthManager.shared
        authManager.clearToken()
    }

    override func tearDown() {
        authManager.clearToken()
        super.tearDown()
    }

    // MARK: - Token Management Tests

    func testSaveToken() {
        let token = AuthToken(
            accessToken: "test-access-token",
            refreshToken: "test-refresh-token",
            deviceId: "device-123",
            deviceName: "Test Device",
            expiresAt: Date().timeIntervalSince1970 + 3600
        )

        authManager.saveToken(token)

        XCTAssertNotNil(authManager.currentToken)
        XCTAssertTrue(authManager.isAuthenticated)
        XCTAssertEqual(authManager.currentToken?.accessToken, "test-access-token")
        XCTAssertEqual(authManager.currentToken?.deviceId, "device-123")
    }

    func testClearToken() {
        let token = AuthToken(
            accessToken: "test-access-token",
            refreshToken: "test-refresh-token",
            deviceId: "device-123",
            deviceName: "Test Device",
            expiresAt: Date().timeIntervalSince1970 + 3600
        )

        authManager.saveToken(token)
        XCTAssertTrue(authManager.isAuthenticated)

        authManager.clearToken()

        XCTAssertNil(authManager.currentToken)
        XCTAssertFalse(authManager.isAuthenticated)
    }

    func testExpiredTokenNotLoaded() {
        let expiredToken = AuthToken(
            accessToken: "expired-token",
            refreshToken: nil,
            deviceId: "device-123",
            deviceName: "Test Device",
            expiresAt: Date().timeIntervalSince1970 - 3600
        )

        authManager.saveToken(expiredToken)
        authManager.clearToken()

        let newAuthManager = AuthManager.shared

        XCTAssertNil(newAuthManager.currentToken)
        XCTAssertFalse(newAuthManager.isAuthenticated)
    }

    func testValidTokenLoaded() {
        let validToken = AuthToken(
            accessToken: "valid-token",
            refreshToken: "refresh-token",
            deviceId: "device-456",
            deviceName: "Valid Device",
            expiresAt: Date().timeIntervalSince1970 + 7200
        )

        authManager.saveToken(validToken)

        let newAuthManager = AuthManager.shared

        XCTAssertNotNil(newAuthManager.currentToken)
        XCTAssertTrue(newAuthManager.isAuthenticated)
        XCTAssertEqual(newAuthManager.currentToken?.accessToken, "valid-token")
    }

    func testGetValidTokenWhenValid() async throws {
        let validToken = AuthToken(
            accessToken: "valid-token",
            refreshToken: "refresh-token",
            deviceId: "device-789",
            deviceName: "Valid Device",
            expiresAt: Date().timeIntervalSince1970 + 7200
        )

        authManager.saveToken(validToken)

        let token = try await authManager.getValidToken()
        XCTAssertEqual(token, "valid-token")
    }

    func testGetValidTokenWhenNotAuthenticated() async {
        authManager.clearToken()

        do {
            _ = try await authManager.getValidToken()
            XCTFail("Expected AuthError.notAuthenticated")
        } catch AuthError.notAuthenticated {
            // Expected
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testAuthHeaderFormat() async throws {
        let token = AuthToken(
            accessToken: "test-token",
            refreshToken: "refresh-token",
            deviceId: "device-999",
            deviceName: "Test Device",
            expiresAt: Date().timeIntervalSince1970 + 3600
        )

        authManager.saveToken(token)

        let header = try await authManager.authHeader()
        XCTAssertEqual(header, "Bearer test-token")
    }

    // MARK: - Server Configuration Tests

    func testSetServerURL() {
        let testURL = URL(string: "ws://192.168.1.100:9847")!
        authManager.setServerURL(testURL)

        XCTAssertEqual(authManager.serverURL, testURL)
        XCTAssertEqual(authManager.restURL, URL(string: "http://192.168.1.100:9847"))
    }

    func testServerURLPersistence() {
        let testURL = URL(string: "ws://example.com:8080")!
        authManager.setServerURL(testURL)

        let newAuthManager = AuthManager.shared
        XCTAssertEqual(newAuthManager.serverURL, testURL)
        XCTAssertEqual(newAuthManager.restURL, URL(string: "http://example.com:8080"))

        // Clean up
        UserDefaults.standard.removeObject(forKey: "jarvis_server_url")
    }

    func testDefaultServerURL() {
        XCTAssertEqual(authManager.serverURL, URL(string: "ws://127.0.0.1:9847"))
        XCTAssertEqual(authManager.restURL, URL(string: "http://127.0.0.1:9847"))
    }

    // MARK: - AuthToken Model Tests

    func testAuthTokenExpiration() {
        let expiredToken = AuthToken(
            accessToken: "expired",
            refreshToken: nil,
            deviceId: "device-1",
            deviceName: "Expired",
            expiresAt: Date().timeIntervalSince1970 - 100
        )

        XCTAssertTrue(expiredToken.isExpired)
    }

    func testAuthTokenNotExpired() {
        let validToken = AuthToken(
            accessToken: "valid",
            refreshToken: nil,
            deviceId: "device-2",
            deviceName: "Valid",
            expiresAt: Date().timeIntervalSince1970 + 3600
        )

        XCTAssertFalse(validToken.isExpired)
    }

    func testAuthTokenExpiresAtDate() {
        let timestamp: Double = 1_700_000_000
        let token = AuthToken(
            accessToken: "test",
            refreshToken: nil,
            deviceId: "device-3",
            deviceName: "Test",
            expiresAt: timestamp
        )

        XCTAssertEqual(token.expiresAtDate, Date(timeIntervalSince1970: timestamp))
    }

    // MARK: - Error Tests

    func testAuthErrorDescriptions() {
        XCTAssertEqual(AuthError.notAuthenticated.errorDescription, "Not authenticated")
        XCTAssertEqual(AuthError.tokenExpired.errorDescription, "Token expired")
        XCTAssertEqual(AuthError.pairingFailed("test").errorDescription, "Pairing failed: test")
        XCTAssertEqual(AuthError.invalidResponse.errorDescription, "Invalid server response")
    }
}
