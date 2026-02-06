import SwiftUI

struct StatusBadge: View {
    @Environment(WebSocketClient.self) private var ws

    var body: some View {
        HStack(spacing: 10) {
            Circle()
                .fill(ws.status.color)
                .frame(width: 12, height: 12)

            Text(ws.status.label)
                .font(.title3)
                .fontWeight(.medium)

            Spacer()

            if ws.isConnected {
                Text("Connected")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else {
                Text("Disconnected")
                    .font(.caption)
                    .foregroundStyle(.red)
            }
        }
    }
}
