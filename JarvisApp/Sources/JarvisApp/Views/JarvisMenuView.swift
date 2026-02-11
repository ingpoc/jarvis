import SwiftUI

enum MenuView: String, CaseIterable {
    case timeline = "Timeline"
    case commandCenter = "Command Center"
}

struct JarvisMenuView: View {
    @Environment(WebSocketClient.self) private var ws
    @State private var selectedView: MenuView = .timeline

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            StatusBadge()
                .padding(.horizontal, 16)
                .padding(.vertical, 12)

            Divider()

            Picker("View", selection: $selectedView) {
                ForEach(MenuView.allCases, id: \.self) { view in
                    Text(view.rawValue).tag(view)
                }
            }
            .pickerStyle(.segmented)
            .padding(.horizontal, 16)
            .padding(.vertical, 8)

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

            switch selectedView {
            case .timeline:
                Text("Timeline")
                    .font(.headline)
                    .padding(.horizontal, 16)
                    .padding(.top, 10)
                    .padding(.bottom, 4)

                TimelineView()
                    .frame(maxHeight: 300)

            case .commandCenter:
                CommandCenterView()
                    .frame(maxHeight: 380)
            }

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
