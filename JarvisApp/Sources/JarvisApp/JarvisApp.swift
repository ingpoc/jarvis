import SwiftUI
import CoreSpotlight

// MARK: - App Container

@main
struct JarvisApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @State private var webSocket = WebSocketClient()

    var body: some Scene {
        MenuBarExtra {
            JarvisMenuView()
                .environment(webSocket)
                .environment(\.webSocket, webSocket)
                .frame(width: 420, height: 520)
                .onAppear {
                    // Initialize Spotlight quick actions on first appearance
                    Task { @MainActor in
                        SpotlightService.shared.indexQuickActions()
                    }
                }
        } label: {
            Image(systemName: "app.fill")
                .symbolRenderingMode(.palette)
                .foregroundStyle(
                    LinearGradient(
                        colors: [.purple, .blue],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
        }
        .menuBarExtraStyle(.window)
    }
}

// MARK: - Environment Key

private struct WebSocketKey: EnvironmentKey {
    static var defaultValue: WebSocketClient {
        WebSocketClient()
    }
}

// MARK: - Environment Extension

extension EnvironmentValues {
    var webSocket: WebSocketClient {
        get { self[WebSocketKey.self] }
        set { self[WebSocketKey.self] = newValue }
    }
}
