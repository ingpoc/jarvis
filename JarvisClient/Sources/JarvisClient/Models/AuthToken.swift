import Foundation

public struct AuthToken: Codable, Sendable {
    public let accessToken: String
    public let refreshToken: String?
    public let deviceId: String
    public let deviceName: String
    public let expiresAt: Double

    public var isExpired: Bool {
        Date().timeIntervalSince1970 > expiresAt
    }

    public var expiresAtDate: Date {
        Date(timeIntervalSince1970: expiresAt)
    }

    public init(
        accessToken: String,
        refreshToken: String? = nil,
        deviceId: String,
        deviceName: String,
        expiresAt: Double
    ) {
        self.accessToken = accessToken
        self.refreshToken = refreshToken
        self.deviceId = deviceId
        self.deviceName = deviceName
        self.expiresAt = expiresAt
    }
}

public struct DeviceInfo: Codable, Identifiable, Sendable {
    public let id: String
    public let name: String
    public let createdAt: Double
    public let lastSeen: Double
    public let isActive: Bool

    public var createdAtDate: Date { Date(timeIntervalSince1970: createdAt) }
    public var lastSeenDate: Date { Date(timeIntervalSince1970: lastSeen) }

    public init(
        id: String,
        name: String,
        createdAt: Double,
        lastSeen: Double,
        isActive: Bool
    ) {
        self.id = id
        self.name = name
        self.createdAt = createdAt
        self.lastSeen = lastSeen
        self.isActive = isActive
    }
}

public struct PairingResponse: Codable, Sendable {
    public let token: String
    public let qrData: String
    public let expiresAt: Double

    enum CodingKeys: String, CodingKey {
        case token
        case qrData = "qr_data"
        case expiresAt = "expires_at"
    }
}

public struct PairingConfirmResponse: Codable, Sendable {
    public let deviceId: String
    public let apiKey: String
    public let jwt: String
    public let expiresAt: Double

    enum CodingKeys: String, CodingKey {
        case deviceId = "device_id"
        case apiKey = "api_key"
        case jwt
        case expiresAt = "expires_at"
    }
}
