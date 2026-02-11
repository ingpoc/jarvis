import SwiftUI

@main
struct JarvisApp: App {
    @State private var ws = WebSocketClient()

    var body: some Scene {
        MenuBarExtra {
            JarvisMenuView()
                .environment(ws)
                .frame(width: 420, height: 520)
        } label: {
            Image(systemName: ws.status.iconName)
                .symbolRenderingMode(.palette)
                .foregroundStyle(ws.status.color)
        }
        .menuBarExtraStyle(.window)
    }

    init() {
        Task {
            await NotificationManager.shared.requestAuthorization()
        }
    }
}
