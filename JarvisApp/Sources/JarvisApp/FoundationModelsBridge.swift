// FoundationModelsBridge.swift
// Provides on-device Foundation Models inference via a local HTTP bridge.
//
// Architecture:
//   Python daemon → HTTP POST localhost:9848 → Swift server → Foundation Models → JSON response
//
// This avoids XPC complexity by using a simple HTTP server that the daemon
// spins up alongside the WebSocket server. Foundation Models require a
// Swift process, so this server runs in the SwiftUI app.
//
// Uses @Generable protocol from FoundationModels framework (macOS 26+).

import Foundation

#if canImport(FoundationModels)
import FoundationModels
#endif

/// Classification result from Foundation Models
struct ClassificationResult: Codable {
    let label: String
    let confidence: Double
    let latencyMs: Double
}

/// Foundation Models bridge providing ultra-fast classification
@available(macOS 26, *)
class FoundationModelsBridge {

    static let shared = FoundationModelsBridge()
    private var httpServer: FoundationModelsHTTPServer?

    /// Port for the Foundation Models HTTP bridge
    let port: UInt16 = 9848

    /// Start the HTTP bridge server
    func start() {
        httpServer = FoundationModelsHTTPServer(port: port)
        httpServer?.start()
        print("[FoundationModels] Bridge started on port \(port)")
    }

    /// Stop the bridge server
    func stop() {
        httpServer?.stop()
        print("[FoundationModels] Bridge stopped")
    }

    /// Classify text using on-device Foundation Models
    func classify(text: String, categories: [String]) async -> ClassificationResult {
        let startTime = CFAbsoluteTimeGetCurrent()

        #if canImport(FoundationModels)
        do {
            let session = LanguageModelSession()

            let prompt = """
            Classify the following text into exactly one of these categories: \(categories.joined(separator: ", ")).
            Respond with ONLY the category name, nothing else.

            Text: \(text.prefix(1000))
            """

            let response = try await session.respond(to: prompt)
            let label = response.content.trimmingCharacters(in: .whitespacesAndNewlines)
            let elapsed = (CFAbsoluteTimeGetCurrent() - startTime) * 1000

            // Validate label is one of the expected categories
            let matchedLabel = categories.first { $0.lowercased() == label.lowercased() } ?? categories.first ?? label

            return ClassificationResult(
                label: matchedLabel,
                confidence: 0.9,
                latencyMs: elapsed
            )
        } catch {
            print("[FoundationModels] Classification error: \(error)")
        }
        #endif

        let elapsed = (CFAbsoluteTimeGetCurrent() - startTime) * 1000
        return ClassificationResult(
            label: categories.first ?? "unknown",
            confidence: 0.0,
            latencyMs: elapsed
        )
    }

    /// Summarize text using Foundation Models
    func summarize(text: String, maxLength: Int = 100) async -> String {
        #if canImport(FoundationModels)
        do {
            let session = LanguageModelSession()
            let prompt = "Summarize in \(maxLength) characters or less:\n\(text.prefix(2000))"
            let response = try await session.respond(to: prompt)
            return String(response.content.prefix(maxLength))
        } catch {
            print("[FoundationModels] Summarize error: \(error)")
        }
        #endif
        return String(text.prefix(maxLength))
    }
}


// MARK: - HTTP Server for Python Bridge

@available(macOS 26, *)
class FoundationModelsHTTPServer {
    let port: UInt16
    private var listener: Any? // NWListener

    init(port: UInt16) {
        self.port = port
    }

    func start() {
        // Use a simple URLSession-based server approach
        // The actual NWListener implementation requires Network framework
        startSimpleServer()
    }

    func stop() {
        // Cleanup
    }

    private func startSimpleServer() {
        // Create a basic HTTP handler using Foundation's built-in networking
        // For production, this would use NWListener from Network framework

        Task {
            // Simple socket server for the Python bridge
            let serverSocket = try? Socket.create(family: .inet, type: .stream, proto: .tcp)
            try? serverSocket?.listen(on: Int(port), maxBacklogSize: 5)

            print("[FoundationModels] HTTP server listening on port \(port)")

            while true {
                guard let clientSocket = try? serverSocket?.acceptClientConnection() else {
                    continue
                }

                Task {
                    await handleConnection(clientSocket)
                }
            }
        }
    }

    private func handleConnection(_ socket: Socket) async {
        defer { socket.close() }

        guard let data = try? socket.readString(),
              let body = extractBody(from: data) else {
            return
        }

        // Parse JSON request
        guard let jsonData = body.data(using: .utf8),
              let request = try? JSONSerialization.jsonObject(with: jsonData) as? [String: Any],
              let action = request["action"] as? String else {
            sendResponse(socket: socket, status: 400, body: #"{"error": "invalid request"}"#)
            return
        }

        let bridge = FoundationModelsBridge.shared

        switch action {
        case "classify":
            let text = request["text"] as? String ?? ""
            let categories = request["categories"] as? [String] ?? ["simple", "moderate", "complex"]
            let result = await bridge.classify(text: text, categories: categories)

            if let responseData = try? JSONEncoder().encode(result),
               let responseStr = String(data: responseData, encoding: .utf8) {
                sendResponse(socket: socket, status: 200, body: responseStr)
            }

        case "summarize":
            let text = request["text"] as? String ?? ""
            let maxLen = request["max_length"] as? Int ?? 100
            let summary = await bridge.summarize(text: text, maxLength: maxLen)
            sendResponse(socket: socket, status: 200, body: #"{"summary": "\#(summary)"}"#)

        case "health":
            sendResponse(socket: socket, status: 200, body: #"{"status": "ok", "model": "foundation-models"}"#)

        default:
            sendResponse(socket: socket, status: 400, body: #"{"error": "unknown action: \#(action)"}"#)
        }
    }

    private func extractBody(from request: String) -> String? {
        // Simple HTTP body extraction
        let parts = request.components(separatedBy: "\r\n\r\n")
        return parts.count > 1 ? parts[1] : nil
    }

    private func sendResponse(socket: Socket, status: Int, body: String) {
        let statusText = status == 200 ? "OK" : "Bad Request"
        let response = """
        HTTP/1.1 \(status) \(statusText)\r
        Content-Type: application/json\r
        Content-Length: \(body.utf8.count)\r
        Connection: close\r
        \r
        \(body)
        """
        try? socket.write(from: response)
    }
}


// MARK: - Minimal Socket Wrapper

/// Minimal socket wrapper for the HTTP server
class Socket {
    enum Family { case inet }
    enum SocketType { case stream }
    enum Proto { case tcp }

    private var fd: Int32 = -1

    static func create(family: Family, type: SocketType, proto: Proto) throws -> Socket {
        let socket = Socket()
        socket.fd = Darwin.socket(AF_INET, SOCK_STREAM, IPPROTO_TCP)
        guard socket.fd >= 0 else { throw SocketError.createFailed }

        // Allow address reuse
        var optval: Int32 = 1
        setsockopt(socket.fd, SOL_SOCKET, SO_REUSEADDR, &optval, socklen_t(MemoryLayout<Int32>.size))

        return socket
    }

    func listen(on port: Int, maxBacklogSize: Int) throws {
        var addr = sockaddr_in()
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_port = UInt16(port).bigEndian
        addr.sin_addr.s_addr = INADDR_LOOPBACK.bigEndian  // localhost only

        let bindResult = withUnsafePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.bind(fd, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        guard bindResult == 0 else { throw SocketError.bindFailed }
        guard Darwin.listen(fd, Int32(maxBacklogSize)) == 0 else { throw SocketError.listenFailed }
    }

    func acceptClientConnection() throws -> Socket {
        let clientFd = Darwin.accept(fd, nil, nil)
        guard clientFd >= 0 else { throw SocketError.acceptFailed }
        let client = Socket()
        client.fd = clientFd
        return client
    }

    func readString() throws -> String? {
        var buffer = [UInt8](repeating: 0, count: 4096)
        let bytesRead = Darwin.read(fd, &buffer, buffer.count)
        guard bytesRead > 0 else { return nil }
        return String(bytes: buffer[0..<bytesRead], encoding: .utf8)
    }

    func write(from string: String) throws {
        let data = Array(string.utf8)
        _ = data.withUnsafeBufferPointer { ptr in
            Darwin.write(fd, ptr.baseAddress, ptr.count)
        }
    }

    func close() {
        if fd >= 0 {
            Darwin.close(fd)
            fd = -1
        }
    }

    enum SocketError: Error {
        case createFailed, bindFailed, listenFailed, acceptFailed
    }
}
