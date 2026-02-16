import Foundation

public final class RESTClient {
    private let baseURL: URL
    private let session: URLSession

    public init(baseURL: URL) {
        self.baseURL = baseURL
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        self.session = URLSession(configuration: config)
    }

    public func initiatePairing(deviceName: String) async throws -> PairingResponse {
        var request = makeRequest(endpoint: "/api/pair", method: "POST")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(["device_name": deviceName])

        let (data, _) = try await session.data(for: request)
        return try decode(data)
    }

    public func confirmPairing(token: String) async throws -> PairingConfirmResponse {
        var request = makeRequest(endpoint: "/api/confirm", method: "POST")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(["token": token])

        let (data, _) = try await session.data(for: request)
        return try decode(data)
    }

    public func getStatus(token: String) async throws -> ServerStatus {
        var request = makeRequest(endpoint: "/api/status", method: "GET")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let (data, _) = try await session.data(for: request)
        return try decode(data)
    }

    public func listDevices(token: String) async throws -> [DeviceInfo] {
        var request = makeRequest(endpoint: "/api/devices", method: "GET")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let (data, _) = try await session.data(for: request)
        let response = try JSONDecoder().decode(DeviceListResponse.self, from: data)
        return response.devices
    }

    public func revokeDevice(token: String, deviceId: String) async throws -> Bool {
        var request = makeRequest(endpoint: "/api/devices/\(deviceId)", method: "DELETE")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let (_, response) = try await session.data(for: request)
        return (response as? HTTPURLResponse)?.statusCode == 200
    }

    private func makeRequest(endpoint: String, method: String) -> URLRequest {
        var request = URLRequest(url: baseURL.appendingPathComponent(endpoint))
        request.httpMethod = method
        request.timeoutInterval = 30
        return request
    }

    private func decode<T: Decodable>(_ data: Data) throws -> T {
        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            if let errorDict = try? JSONDecoder().decode([String: String].self, from: data),
               let errorMessage = errorDict["error"] {
                throw APIError.serverError(errorMessage)
            }
            throw error
        }
    }
}

// MARK: - Response Types

public struct ServerStatus: Codable, Sendable {
    public let status: String
    public let connectedDevices: Int
    public let version: String

    enum CodingKeys: String, CodingKey {
        case status, version
        case connectedDevices = "connected_devices"
    }
}

struct DeviceListResponse: Codable {
    let devices: [DeviceInfo]
}

// MARK: - Errors

public enum APIError: LocalizedError {
    case serverError(String)
    case invalidURL
    case decodingError(Error)
    case networkError(Error)

    public var errorDescription: String? {
        switch self {
        case .serverError(let message):
            return message
        case .invalidURL:
            return "Invalid URL"
        case .decodingError(let error):
            return "Decoding error: \(error.localizedDescription)"
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        }
    }
}
