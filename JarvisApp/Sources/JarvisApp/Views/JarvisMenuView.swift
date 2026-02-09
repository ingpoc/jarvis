import SwiftUI

struct JarvisMenuView: View {
    @Environment(WebSocketClient.self) private var ws

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            StatusBadge()
                .padding(.horizontal, 16)
                .padding(.vertical, 12)

            Divider()

            // Command input
            CommandInputView()
                .padding(.horizontal, 16)
                .padding(.vertical, 8)

            Divider()

            // Pending approvals section
            if !ws.pendingApprovals.isEmpty {
                HStack {
                    Text("Pending Approvals")
                        .font(.headline)
                    Spacer()
                    Text("\(ws.pendingApprovals.count)")
                        .font(.caption)
                        .fontWeight(.bold)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 2)
                        .background(.orange.opacity(0.2))
                        .cornerRadius(10)
                }
                .padding(.horizontal, 16)
                .padding(.top, 10)
                .padding(.bottom, 4)

                ApprovalView()
                    .padding(.horizontal, 16)
                    .padding(.bottom, 8)

                Divider()
            }

            // Timeline section
            HStack {
                Text("Timeline")
                    .font(.headline)
                Spacer()
                if !ws.events.isEmpty {
                    Text("\(ws.events.count) events")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 10)
            .padding(.bottom, 4)

            TimelineView()
                .frame(maxHeight: 300)

            Divider()

            // Bottom bar
            HStack {
                Button(action: {
                    ws.sendCommand(action: "get_status")
                    ws.sendCommand(action: "get_timeline")
                }) {
                    Label("Refresh", systemImage: "arrow.clockwise")
                }
                .buttonStyle(.bordered)
                .controlSize(.small)

                Spacer()

                Button(action: {
                    NSApplication.shared.terminate(nil)
                }) {
                    Label("Quit", systemImage: "power")
                }
                .buttonStyle(.bordered)
                .tint(.red)
                .controlSize(.small)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
        }
        .onAppear {
            ws.connect()
        }
    }
}
