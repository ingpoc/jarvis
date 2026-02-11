import SwiftUI

struct StatusBadge: View {
    @Environment(WebSocketClient.self) private var ws

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: ws.status.iconName)
                .foregroundStyle(ws.status.color)
                .font(.title3)

            Text(ws.status.label)
                .font(.title3)
                .fontWeight(.medium)

            Spacer()

            if ws.isConnected {
                HStack(spacing: 4) {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                    Text("Connected")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            } else {
                HStack(spacing: 4) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(.red)
                    Text("Disconnected")
                        .font(.caption)
                        .foregroundStyle(.red)
                }
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Jarvis status")
        .accessibilityValue("\(ws.status.label), \(ws.isConnected ? "Connected" : "Disconnected")")
    }
}
