import Foundation
import Observation

@available(macOS 14, iOS 17, *)
@Observable
public final class AuthManager {
    public private(set) var currentToken: AuthToken?
    public private(set) var isAuthenticated = false
    public private(set) var serverURL: URL = URL(string: "wss://localhost:9848")!
    public private(set) var restURL: URL = URL(string: "http://localhost:9849")!

    private let tokenKey = "jarvis_auth_token"
    private let serverURLKey = "jarvis_server_url"

    public static let shared = AuthManager()

    private init() {
        loadSavedToken()
        loadSavedServerURL()
    }

    // MARK: - Server Configuration

    public func setServerURL(_ url: URL) {
        self.serverURL = url
        self.restURL = URL(string: "http://\(url.host ?? "localhost"):9849")!
        UserDefaults.standard.set(url.absoluteString, forKey: serverURLKey)
    }

    private func loadSavedServerURL() {
        if let savedString = UserDefaults.standard.string(forKey: serverURLKey),
           let url = URL(string: savedString) {
            self.serverURL = url
            self.restURL = URL(string: "http://\(url.host ?? "localhost"):9849")!
        }
    }

    // MARK: - Token Management

    public func saveToken(_ token: AuthToken) {
        self.currentToken = token
        self.isAuthenticated = true

        if let data = try? JSONEncoder().encode(token) {
            UserDefaults.standard.set(data, forKey: tokenKey)
        }
    }

    public func clearToken() {
        self.currentToken = nil
        self.isAuthenticated = false
        UserDefaults.standard.removeObject(forKey: tokenKey)
    }

    private func loadSavedToken() {
        guard let data = UserDefaults.standard.data(forKey: tokenKey),
              let token = try? JSONDecoder().decode(AuthToken.self, from: data) else { return }

        if !token.isExpired {
            self.currentToken = token
            self.isAuthenticated = true
        } else {
            UserDefaults.standard.removeObject(forKey: tokenKey)
        }
    }

    // MARK: - Pairing

    public func initiatePairing(deviceName: String) async throws -> PairingResponse {
        let client = RESTClient(baseURL: restURL)
        return try await client.initiatePairing(deviceName: deviceName)
    }

    public func confirmPairing(token: String) async throws {
        let client = RESTClient(baseURL: restURL)
        let response = try await client.confirmPairing(token: token)

        let authToken = AuthToken(
            accessToken: response.jwt,
            refreshToken: nil,
            deviceId: response.deviceId,
            deviceName: "",  // Will be filled from token
            expiresAt: response.expiresAt
        )

        saveToken(authToken)
    }

    // MARK: - Device Management

    public func listDevices() async throws -> [DeviceInfo] {
        guard let token = currentToken else { throw AuthError.notAuthenticated }
        let client = RESTClient(baseURL: restURL)
        return try await client.listDevices(token: token.accessToken)
    }

    public func revokeDevice(deviceId: String) async throws -> Bool {
        guard let token = currentToken else { throw AuthError.notAuthenticated }
        let client = RESTClient(baseURL: restURL)
        return try await client.revokeDevice(token: token.accessToken, deviceId: deviceId)
    }

    // MARK: - Authentication Header

    public func authHeader() -> String? {
        guard let token = currentToken else { return nil }
        return "Bearer \(token.accessToken)"
    }
}

// MARK: - Errors

public enum AuthError: LocalizedError {
    case notAuthenticated
    case tokenExpired
    case pairingFailed(String)
    case invalidResponse

    public var errorDescription: String? {
        switch self {
        case .notAuthenticated:
            return "Not authenticated"
        case .tokenExpired:
            return "Token expired"
        case .pairingFailed(let message):
            return "Pairing failed: \(message)"
        case .invalidResponse:
            return "Invalid server response"
        }
    }
}
