import Foundation
import Observation

@available(macOS 14, iOS 17, *)
@Observable
public final class AuthManager {
    public private(set) var currentToken: AuthToken?
    public private(set) var isAuthenticated = false
    public private(set) var serverURL: URL
    public private(set) var restURL: URL

    private let tokenKey = "jarvis_auth_token"
    private let serverURLKey = "jarvis_server_url"

    public static let shared = AuthManager()

    private init() {
        // Safe defaults - never force unwrap
        guard let defaultServerURL = URL(string: "ws://127.0.0.1:9847"),
              let defaultRestURL = URL(string: "http://127.0.0.1:9847") else {
            fatalError("Invalid default URLs - this should never happen")
        }
        self.serverURL = defaultServerURL
        self.restURL = defaultRestURL
        loadSavedToken()
        loadSavedServerURL()
    }

    // MARK: - Server Configuration

    public func setServerURL(_ url: URL) {
        self.serverURL = url
        // Derive REST URL from WebSocket URL safely
        if let host = url.host,
           let port = url.port,
           let restURL = URL(string: "http://\(host):\(port)") {
            self.restURL = restURL
        } else {
            // Fallback to default if URL parsing fails
            guard let fallbackURL = URL(string: "http://127.0.0.1:9847") else {
                self.restURL = URL(string: "http://127.0.0.1:9847")! // Safe fallback in init
                return
            }
            self.restURL = fallbackURL
        }
        UserDefaults.standard.set(url.absoluteString, forKey: serverURLKey)
    }

    private func loadSavedServerURL() {
        guard let savedString = UserDefaults.standard.string(forKey: serverURLKey),
              let url = URL(string: savedString) else {
            return
        }
        self.serverURL = url
        if let host = url.host,
           let port = url.port,
           let restURL = URL(string: "http://\(host):\(port)") {
            self.restURL = restURL
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
        let token = try await getValidToken()
        let client = RESTClient(baseURL: restURL)
        return try await client.listDevices(token: token)
    }

    public func revokeDevice(deviceId: String) async throws -> Bool {
        let token = try await getValidToken()
        let client = RESTClient(baseURL: restURL)
        return try await client.revokeDevice(token: token, deviceId: deviceId)
    }

    // MARK: - Authentication Header

    public func getValidToken() async throws -> String {
        guard let token = currentToken else {
            throw AuthError.notAuthenticated
        }

        // Add 5 minute buffer to refresh before actual expiration
        let buffer: TimeInterval = 300
        let isExpiringSoon = Date().timeIntervalSince1970 > (token.expiresAt - buffer)

        if !isExpiringSoon {
            return token.accessToken
        }

        // Token is expiring soon, attempt refresh
        guard let refreshToken = token.refreshToken else {
            // No refresh token available, clear auth and throw
            clearToken()
            throw AuthError.tokenExpired
        }

        do {
            let client = RESTClient(baseURL: restURL)
            let response = try await client.refreshToken(refreshToken: refreshToken)

            let newToken = AuthToken(
                accessToken: response.accessToken,
                refreshToken: response.refreshToken ?? refreshToken,
                deviceId: token.deviceId,
                deviceName: token.deviceName,
                expiresAt: response.expiresAt
            )

            saveToken(newToken)
            return newToken.accessToken
        } catch {
            // Refresh failed - clear token and require re-authentication
            clearToken()
            throw AuthError.tokenExpired
        }
    }

    public func authHeader() async throws -> String {
        let token = try await getValidToken()
        return "Bearer \(token)"
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
