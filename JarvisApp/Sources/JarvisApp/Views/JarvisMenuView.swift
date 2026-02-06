import SwiftUI

struct JarvisMenuView: View {
    @Environment(WebSocketClient.self) private var ws

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            StatusBadge()
                .padding(.horizontal, 16)
                .padding(.vertical, 12)

            Divider()

            if !ws.pendingApprovals.isEmpty {
                Text("Pending Approvals")
                    .font(.headline)
                    .padding(.horizontal, 16)
                    .padding(.top, 10)
                    .padding(.bottom, 4)

                ApprovalView()
                    .padding(.horizontal, 16)
                    .padding(.bottom, 8)

                Divider()
            }

            Text("Timeline")
                .font(.headline)
                .padding(.horizontal, 16)
                .padding(.top, 10)
                .padding(.bottom, 4)

            TimelineView()
                .frame(maxHeight: 300)

            Divider()

            HStack {
                Button("Refresh") {
                    ws.sendCommand(action: "get_status")
                    ws.sendCommand(action: "get_timeline")
                }
                .buttonStyle(.bordered)

                Spacer()

                Button("Quit") {
                    NSApplication.shared.terminate(nil)
                }
                .buttonStyle(.bordered)
                .tint(.red)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
        }
        .onAppear {
            ws.connect()
        }
    }
}
