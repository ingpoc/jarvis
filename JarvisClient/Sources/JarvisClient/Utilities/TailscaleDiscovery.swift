import Foundation

/// Discover Jarvis server via Tailscale
public final class TailscaleDiscovery {
    private let tailscaleIPRange = "100."
    private let commonPorts = [9848, 9849]

    public init() {}

    /// Discover Tailscale IP by checking local network interfaces
    public func discoverTailscaleIP() async -> URL? {
        // Try to get Tailscale IP from subprocess (macOS/iOS has limitations)
        #if os(macOS)
        return await discoverViaSubprocess()
        #else
        return nil
        #endif
    }

    /// Try to find server via mDNS/Bonjour
    public func discoverViaBonjour() async -> URL? {
        // Bonjour discovery implementation
        // For now, return common Tailscale configuration
        return URL(string: "wss://100.0.0.1:9848")
    }

    #if os(macOS)
    private func discoverViaSubprocess() async -> URL? {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/tailscale")
        task.arguments = ["ip", "-4"]

        let pipe = Pipe()
        task.standardOutput = pipe

        do {
            try task.run()
            task.waitUntilExit()

            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            if let output = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines),
               !output.isEmpty {
                return URL(string: "wss://\(output):9848")
            }
        } catch {
            return nil
        }

        return nil
    }
    #endif

    /// Get Tailscale status
    public func getTailscaleStatus() async -> TailscaleStatus? {
        #if os(macOS)
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/tailscale")
        task.arguments = ["status", "--json"]

        let pipe = Pipe()
        task.standardOutput = pipe

        do {
            try task.run()
            task.waitUntilExit()

            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            return try? JSONDecoder().decode(TailscaleStatus.self, from: data)
        } catch {
            return nil
        }
        #else
        return nil
        #endif
    }
}

// MARK: - Status Types

public struct TailscaleStatus: Codable {
    public let backendState: String
    public let selfInfo: TailscalePeer?

    enum CodingKeys: String, CodingKey {
        case backendState = "BackendState"
        case selfInfo = "Self"
    }
}

public struct TailscalePeer: Codable {
    public let hostname: String
    public let tailscaleIPs: [String]

    enum CodingKeys: String, CodingKey {
        case hostname = "HostName"
        case tailscaleIPs = "TailscaleIPs"
    }
}
