import SwiftUI

struct StatusBadge: View {
    @Environment(WebSocketClient.self) private var ws

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 10) {
                Image(systemName: ws.status.iconName)
                    .font(.title2)
                    .foregroundStyle(ws.status.color)
                    .symbolEffect(.pulse, isActive: ws.status == .building)

                VStack(alignment: .leading, spacing: 2) {
                    Text(ws.status.label)
                        .font(.title3)
                        .fontWeight(.medium)

                    if let feature = ws.currentFeature {
                        Text(feature)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    }
                }

                Spacer()

                if ws.isConnected {
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
            if ws.trustInfo != nil || ws.budgetInfo != nil {
                HStack(spacing: 16) {
                    if let trust = ws.trustInfo, let tier = trust.tier {
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

                    if let budget = ws.budgetInfo, let session = budget.session {
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
