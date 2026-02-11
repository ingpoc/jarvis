import SwiftUI

struct StatusBadge: View {
    @Environment(\.webSocket) private var webSocket

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: webSocket.status.iconName)
                .foregroundStyle(webSocket.status.color)
                .font(.title3)

            Text(webSocket.status.label)
                .font(.title3)
                .fontWeight(.medium)

            Spacer()

            if webSocket.connectionState == .connected {
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
        .accessibilityValue("\(webSocket.status.label), \(webSocket.connectionState == .connected ? "Connected" : "Disconnected")")
    }
}
