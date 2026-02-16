import SwiftUI

struct StatusBadge: View {
    @Environment(\.webSocket) private var webSocket

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 10) {
                Image(systemName: webSocket.status.iconName)
                    .font(.title2)
                    .foregroundStyle(webSocket.status.color)
                    .symbolEffect(.pulse, isActive: webSocket.status == .building)

                VStack(alignment: .leading, spacing: 2) {
                    Text(webSocket.status.label)
                        .font(.title3)
                        .fontWeight(.medium)

                    if let feature = webSocket.currentFeature {
                        Text(feature)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    }
                }

                Spacer()

                if webSocket.isConnected {
                    Circle()
                        .fill(.green)
                        .frame(width: 8, height: 8)
                } else {
                    HStack(spacing: 4) {
                        Circle()
                            .fill(.red)
                            .frame(width: 8, height: 8)
                        Text("Offline")
                            .font(.caption2)
                            .foregroundStyle(.red)
                    }
                }
            }

            // Trust and Budget row
            if webSocket.trustInfo != nil || webSocket.budgetInfo != nil {
                HStack(spacing: 16) {
                    if let trust = webSocket.trustInfo, let tier = trust.tier {
                        HStack(spacing: 4) {
                            Image(systemName: "shield.fill")
                                .font(.caption2)
                                .foregroundStyle(trustColor(tier: tier))
                            Text("T\(tier)")
                                .font(.system(.caption, design: .monospaced))
                                .foregroundStyle(trustColor(tier: tier))
                            if let name = trust.tierName {
                                Text(name)
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }

                    if let budget = webSocket.budgetInfo, let session = budget.session {
                        HStack(spacing: 4) {
                            Image(systemName: "dollarsign.circle")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                            Text(session)
                                .font(.system(.caption, design: .monospaced))
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Jarvis status")
        .accessibilityValue("\(webSocket.status.label), \(webSocket.connectionState == .connected ? "Connected" : "Disconnected")")
    }

    private func trustColor(tier: Int) -> Color {
        switch tier {
        case 0: .gray
        case 1: .blue
        case 2: .green
        case 3: .orange
        case 4: .purple
        default: .secondary
        }
    }
}
