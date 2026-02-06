import XCTest
@testable import JarvisClient

@available(macOS 14, iOS 17, *)
final class RESTClientTests: XCTestCase {

    var restClient: RESTClient!

    override func setUp() {
        super.setUp()
        restClient = RESTClient(baseURL: URL(string: "http://127.0.0.1:9847")!)
    }

    override func tearDown() {
        restClient = nil
        super.tearDown()
    }

    // MARK: - Initialization Tests

    func testInitialization() {
        let client = RESTClient(baseURL: URL(string: "http://example.com:8080")!)

        XCTAssertNotNil(client)
    }

    // MARK: - Model Tests

    func testPairingResponseModel() {
        let response = PairingResponse(
            token: "pairing-token-123",
            qrData: "QR_CODE_DATA",
            expiresAt: 1_700_000_000
        )

        XCTAssertEqual(response.token, "pairing-token-123")
        XCTAssertEqual(response.qrData, "QR_CODE_DATA")
        XCTAssertEqual(response.expiresAt, 1_700_000_000)
    }

    func testPairingConfirmResponseModel() {
        let response = PairingConfirmResponse(
            deviceId: "device-abc-123",
            apiKey: "api-key-xyz",
            jwt: "jwt-token-123",
            expiresAt: 1_700_000_000
        )

        XCTAssertEqual(response.deviceId, "device-abc-123")
        XCTAssertEqual(response.apiKey, "api-key-xyz")
        XCTAssertEqual(response.jwt, "jwt-token-123")
        XCTAssertEqual(response.expiresAt, 1_700_000_000)
    }

    func testServerStatusModel() {
        let status = ServerStatus(
            status: "running",
            connectedDevices: 5,
            version: "1.0.0"
        )

        XCTAssertEqual(status.status, "running")
        XCTAssertEqual(status.connectedDevices, 5)
        XCTAssertEqual(status.version, "1.0.0")
    }

    func testDeviceInfoModel() {
        let device = DeviceInfo(
            id: "device-1",
            name: "Test Device",
            createdAt: 1_700_000_000,
            lastSeen: 1_700_000_000,
            isActive: true
        )

        XCTAssertEqual(device.id, "device-1")
        XCTAssertEqual(device.name, "Test Device")
        XCTAssertTrue(device.isActive)
        XCTAssertEqual(device.createdAtDate, Date(timeIntervalSince1970: 1_700_000_000))
        XCTAssertEqual(device.lastSeenDate, Date(timeIntervalSince1970: 1_700_000_000))
    }

    func testRefreshResponseModel() {
        let response = RefreshResponse(
            accessToken: "new-access-token",
            refreshToken: "new-refresh-token",
            expiresAt: 1_700_000_000
        )

        XCTAssertEqual(response.accessToken, "new-access-token")
        XCTAssertEqual(response.refreshToken, "new-refresh-token")
        XCTAssertEqual(response.expiresAt, 1_700_000_000)
    }

    func testRefreshResponseWithoutRefreshToken() {
        let response = RefreshResponse(
            accessToken: "new-access-token",
            refreshToken: nil,
            expiresAt: 1_700_000_000
        )

        XCTAssertEqual(response.accessToken, "new-access-token")
        XCTAssertNil(response.refreshToken)
    }

    // MARK: - Coding Tests

    func testPairingResponseEncodingDecoding() throws {
        let response = PairingResponse(
            token: "test-token",
            qrData: "test-qr",
            expiresAt: 1_700_000_000
        )

        let encoder = JSONEncoder()
        let data = try encoder.encode(response)

        let decoder = JSONDecoder()
        let decoded = try decoder.decode(PairingResponse.self, from: data)

        XCTAssertEqual(decoded.token, response.token)
        XCTAssertEqual(decoded.qrData, response.qrData)
        XCTAssertEqual(decoded.expiresAt, response.expiresAt)
    }

    func testPairingConfirmResponseEncodingDecoding() throws {
        let response = PairingConfirmResponse(
            deviceId: "device-123",
            apiKey: "key-123",
            jwt: "jwt-123",
            expiresAt: 1_700_000_000
        )

        let encoder = JSONEncoder()
        let data = try encoder.encode(response)

        let decoder = JSONDecoder()
        let decoded = try decoder.decode(PairingConfirmResponse.self, from: data)

        XCTAssertEqual(decoded.deviceId, response.deviceId)
        XCTAssertEqual(decoded.apiKey, response.apiKey)
        XCTAssertEqual(decoded.jwt, response.jwt)
        XCTAssertEqual(decoded.expiresAt, response.expiresAt)
    }

    func testServerStatusEncodingDecoding() throws {
        let status = ServerStatus(
            status: "running",
            connectedDevices: 3,
            version: "2.0.0"
        )

        let encoder = JSONEncoder()
        let data = try encoder.encode(status)

        let decoder = JSONDecoder()
        let decoded = try decoder.decode(ServerStatus.self, from: data)

        XCTAssertEqual(decoded.status, status.status)
        XCTAssertEqual(decoded.connectedDevices, status.connectedDevices)
        XCTAssertEqual(decoded.version, status.version)
    }

    func testDeviceInfoEncodingDecoding() throws {
        let device = DeviceInfo(
            id: "device-xyz",
            name: "My Device",
            createdAt: 1_700_000_000,
            lastSeen: 1_700_003_600,
            isActive: true
        )

        let encoder = JSONEncoder()
        let data = try encoder.encode(device)

        let decoder = JSONDecoder()
        let decoded = try decoder.decode(DeviceInfo.self, from: data)

        XCTAssertEqual(decoded.id, device.id)
        XCTAssertEqual(decoded.name, device.name)
        XCTAssertEqual(decoded.createdAt, device.createdAt)
        XCTAssertEqual(decoded.lastSeen, device.lastSeen)
        XCTAssertEqual(decoded.isActive, device.isActive)
    }

    func testRefreshResponseEncodingDecoding() throws {
        let response = RefreshResponse(
            accessToken: "access-token-123",
            refreshToken: "refresh-token-123",
            expiresAt: 1_700_000_000
        )

        let encoder = JSONEncoder()
        let data = try encoder.encode(response)

        let decoder = JSONDecoder()
        let decoded = try decoder.decode(RefreshResponse.self, from: data)

        XCTAssertEqual(decoded.accessToken, response.accessToken)
        XCTAssertEqual(decoded.refreshToken, response.refreshToken)
        XCTAssertEqual(decoded.expiresAt, response.expiresAt)
    }

    func testAuthTokenEncodingDecoding() throws {
        let token = AuthToken(
            accessToken: "access-token",
            refreshToken: "refresh-token",
            deviceId: "device-123",
            deviceName: "My Device",
            expiresAt: 1_700_000_000
        )

        let encoder = JSONEncoder()
        let data = try encoder.encode(token)

        let decoder = JSONDecoder()
        let decoded = try decoder.decode(AuthToken.self, from: data)

        XCTAssertEqual(decoded.accessToken, token.accessToken)
        XCTAssertEqual(decoded.refreshToken, token.refreshToken)
        XCTAssertEqual(decoded.deviceId, token.deviceId)
        XCTAssertEqual(decoded.deviceName, token.deviceName)
        XCTAssertEqual(decoded.expiresAt, token.expiresAt)
    }

    // MARK: - APIError Tests

    func testAPIErrorDescriptions() {
        XCTAssertEqual(APIError.serverError("Server failed").errorDescription, "Server failed")
        XCTAssertEqual(APIError.invalidURL.errorDescription, "Invalid URL")
        XCTAssertEqual(APIError.decodingError("Parse error").errorDescription, "Decoding error: Parse error")
        XCTAssertEqual(APIError.networkError("Connection failed").errorDescription, "Network error: Connection failed")
    }

    // MARK: - JSON Decoding Tests

    func testPairingResponseFromJSON() throws {
        let json = """
        {
            "token": "pairing-token",
            "qr_data": "qr-data-string",
            "expires_at": 1700000000
        }
        """

        let data = json.data(using: .utf8)!
        let decoder = JSONDecoder()
        let response = try decoder.decode(PairingResponse.self, from: data)

        XCTAssertEqual(response.token, "pairing-token")
        XCTAssertEqual(response.qrData, "qr-data-string")
        XCTAssertEqual(response.expiresAt, 1_700_000_000)
    }

    func testPairingConfirmResponseFromJSON() throws {
        let json = """
        {
            "device_id": "device-123",
            "api_key": "api-key-123",
            "jwt": "jwt-token",
            "expires_at": 1700000000
        }
        """

        let data = json.data(using: .utf8)!
        let decoder = JSONDecoder()
        let response = try decoder.decode(PairingConfirmResponse.self, from: data)

        XCTAssertEqual(response.deviceId, "device-123")
        XCTAssertEqual(response.apiKey, "api-key-123")
        XCTAssertEqual(response.jwt, "jwt-token")
        XCTAssertEqual(response.expiresAt, 1_700_000_000)
    }

    func testServerStatusFromJSON() throws {
        let json = """
        {
            "status": "running",
            "connected_devices": 7,
            "version": "1.5.0"
        }
        """

        let data = json.data(using: .utf8)!
        let decoder = JSONDecoder()
        let status = try decoder.decode(ServerStatus.self, from: data)

        XCTAssertEqual(status.status, "running")
        XCTAssertEqual(status.connectedDevices, 7)
        XCTAssertEqual(status.version, "1.5.0")
    }

    func testDeviceInfoFromJSON() throws {
        let json = """
        {
            "id": "device-abc",
            "name": "Test Device",
            "createdAt": 1700000000,
            "lastSeen": 1700003600,
            "isActive": true
        }
        """

        let data = json.data(using: .utf8)!
        let decoder = JSONDecoder()
        let device = try decoder.decode(DeviceInfo.self, from: data)

        XCTAssertEqual(device.id, "device-abc")
        XCTAssertEqual(device.name, "Test Device")
        XCTAssertEqual(device.createdAt, 1_700_000_000)
        XCTAssertEqual(device.lastSeen, 1_700_003_600)
        XCTAssertTrue(device.isActive)
    }

    func testRefreshResponseFromJSON() throws {
        let json = """
        {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_at": 1700000000
        }
        """

        let data = json.data(using: .utf8)!
        let decoder = JSONDecoder()
        let response = try decoder.decode(RefreshResponse.self, from: data)

        XCTAssertEqual(response.accessToken, "new-access")
        XCTAssertEqual(response.refreshToken, "new-refresh")
        XCTAssertEqual(response.expiresAt, 1_700_000_000)
    }

    func testRefreshResponseWithoutRefreshTokenFromJSON() throws {
        let json = """
        {
            "access_token": "new-access",
            "expires_at": 1700000000
        }
        """

        let data = json.data(using: .utf8)!
        let decoder = JSONDecoder()
        let response = try decoder.decode(RefreshResponse.self, from: data)

        XCTAssertEqual(response.accessToken, "new-access")
        XCTAssertNil(response.refreshToken)
    }
}
