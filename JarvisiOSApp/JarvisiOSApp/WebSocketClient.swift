//
//  WebSocketClient.swift
//  JarvisiOSApp
//
//  WebSocket client for real-time Jarvis communication
//

import Foundation
import Combine

@MainActor
class WebSocketClient: NSObject, ObservableObject {
    @Published var isConnected = false
    @Published var receivedMessage = ""

    private var webSocket: URLSessionWebSocketTask?
    private var urlSession: URLSession?

    func connect(to url: String) {
        guard let URL = URL(string: url) else { return }

        let configuration = URLSessionConfiguration.default
        urlSession = URLSession(configuration: configuration, delegate: self, delegateQueue: nil)

        webSocket = urlSession?.webSocketTask(with: URL)
        webSocket?.resume()

        receiveMessage()
    }

    func disconnect() {
        webSocket?.cancel(with: .goingAway, reason: nil)
        isConnected = false
    }

    func send(_ text: String) {
        let message = URLSessionWebSocketTask.Message.string(text)
        webSocket?.send(message) { error in
            if let error = error {
                print("WebSocket send error: \(error)")
            }
        }
    }

    private func receiveMessage() {
        webSocket?.receive { [weak self] result in
            Task { @MainActor in
                switch result {
                case .success(let message):
                    switch message {
                    case .string(let text):
                        self?.receivedMessage = text
                        self?.isConnected = true
                    case .data(let data):
                        self?.receivedMessage = String(data: data, encoding: .utf8) ?? ""
                        self?.isConnected = true
                    @unknown default:
                        break
                    }
                    self?.receiveMessage()
                case .failure(_):
                    self?.isConnected = false
                }
            }
        }
    }
}

extension WebSocketClient: URLSessionWebSocketDelegate {
    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didOpenWithProtocol protocol: String?) {
        isConnected = true
    }

    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didCloseWith closeCode: URLSessionWebSocketTask.CloseCode, reason: Data?) {
        isConnected = false
    }
}
