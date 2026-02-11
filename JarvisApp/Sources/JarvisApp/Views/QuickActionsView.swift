import SwiftUI
import UniformTypeIdentifiers

// MARK: - Quick Actions View

struct QuickActionsView: View {
    @Environment(\.webSocket) private var webSocket

    var body: some View {
        Menu {
            ForEach(QuickAction.allCases.filter { $0.rawValue != "Toggle Menu Bar" }, id: \.rawValue) { action in
                Button {
                    Task {
                        await executeAction(action)
                    }
                } label: {
                    Label(action.rawValue, systemImage: action.icon)
                }
            }

            Divider()

            Menu("Developer") {
                Button("Run Tests") {
                    Task { await executeAction(.runTests) }
                }
                .keyboardShortcut("k", modifiers: [.command, .option])

                Button("Build Project") {
                    Task { await executeAction(.buildProject) }
                }
                .keyboardShortcut("b", modifiers: [.command, .option])

                Button("Git Status") {
                    Task { await executeAction(.gitStatus) }
                }
                .keyboardShortcut("g", modifiers: [.command, .option])
            }

            Menu("Navigation") {
                Button("Show Timeline") {
                    Task { await executeAction(.showTimeline) }
                }
                .keyboardShortcut("t", modifiers: [.command, .option])

                Button("Show Command Center") {
                    Task { await executeAction(.showCommandCenter) }
                }
                .keyboardShortcut("c", modifiers: [.command, .option])

                Button("Show Approvals") {
                    Task { await executeAction(.showApprovals) }
                }
                .keyboardShortcut("a", modifiers: [.command, .option])
            }
        } label: {
            Image(systemName: "ellipsis.circle")
                .foregroundStyle(.secondary)
        }
    }

    private func executeAction(_ action: QuickAction) async {
        switch action {
        case .refresh:
            try? await webSocket.sendWithoutResponse(action: "get_status", data: nil)
            try? await webSocket.sendWithoutResponse(action: "get_containers", data: nil)

        case .runTests:
            try? await webSocket.sendWithoutResponse(action: "run_tests", data: nil)

        case .buildProject:
            try? await webSocket.sendWithoutResponse(action: "build_project", data: nil)

        case .gitStatus:
            try? await webSocket.sendWithoutResponse(action: "git_status", data: nil)

        default:
            break
        }
    }
}

// MARK: - Quick Actions Grid

struct QuickActionsGrid: View {
    @Environment(\.webSocket) private var webSocket

    private let commonActions: [QuickAction] = [
        .refresh, .runTests, .buildProject, .gitStatus
    ]

    var body: some View {
        ScrollView {
            LazyVGrid(
                columns: [
                    GridItem(.flexible()),
                    GridItem(.flexible())
                ],
                spacing: 8
            ) {
                ForEach(commonActions) { action in
                    Button {
                        Task {
                            await executeAction(action)
                        }
                    } label: {
                        Label(action.rawValue, systemImage: action.icon)
                            .font(.caption)
                    }
                    .buttonStyle(.bordered)
                    .frame(maxWidth: .infinity)
                }
            }
            .padding()
        }
    }

    private func executeAction(_ action: QuickAction) async {
        switch action {
        case .refresh:
            try? await webSocket.sendWithoutResponse(action: "get_status", data: nil)
            try? await webSocket.sendWithoutResponse(action: "get_containers", data: nil)

        case .runTests:
            try? await webSocket.sendWithoutResponse(action: "run_tests", data: nil)

        case .buildProject:
            try? await webSocket.sendWithoutResponse(action: "build_project", data: nil)

        case .gitStatus:
            try? await webSocket.sendWithoutResponse(action: "git_status", data: nil)

        default:
            break
        }
    }
}

// MARK: - Drop Delegate for File Handling

struct FileDropDelegate: DropDelegate {
    let webSocket: any WebSocketClientProtocol
    let onFileDropped: ([URL]) -> Void

    func validateDrop(info: DropInfo) -> Bool {
        info.hasItemsConforming(to: [.fileURL])
    }

    func performDrop(info: DropInfo) -> Bool {
        let providers = info.itemProviders(for: [.fileURL])
        guard !providers.isEmpty else {
            return false
        }

        var urls: [URL] = []

        for provider in providers {
            _ = provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier) { item, error in
                if let error = error {
                    print("Error loading item: \(error)")
                    return
                }

                if let url = item as? URL {
                    urls.append(url)
                }
            }
        }

        if !urls.isEmpty {
            DispatchQueue.main.async {
                onFileDropped(urls)
            }
        }

        return !urls.isEmpty
    }
}
