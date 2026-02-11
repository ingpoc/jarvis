import SwiftUI
import UniformTypeIdentifiers

// MARK: - Menu View Options

enum MenuView: String, CaseIterable, Identifiable {
    case timeline = "Timeline"
    case commandCenter = "Command Center"
    case quickActions = "Quick Actions"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .timeline: "clock.arrow.circlepath"
        case .commandCenter: "chart.bar.doc.horizontal"
        case .quickActions: "bolt.circle"
        }
    }
}

// MARK: - Menu View

struct JarvisMenuView: View {
    @Environment(\.webSocket) private var webSocket
    @State private var selectedView: MenuView = .timeline
    @State private var droppedFiles: [URL] = []
    @State private var showDropOverlay = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Status Header with Quick Actions Menu
            HStack {
                StatusBadge()
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)

                Spacer()

                QuickActionsView()
                    .padding(.trailing, 16)
            }

            Divider()

            // View Picker
            Picker("View", selection: $selectedView) {
                ForEach(MenuView.allCases) { view in
                    Label(view.rawValue, systemImage: view.icon)
                        .tag(view)
                }
            }
            .pickerStyle(.segmented)
            .padding(.horizontal, 16)
            .padding(.vertical, 8)

            Divider()

            // Pending Approvals Section
            if !webSocket.pendingApprovals.isEmpty {
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

            // Content Views
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

            case .quickActions:
                Text("Quick Actions")
                    .font(.headline)
                    .padding(.horizontal, 16)
                    .padding(.top, 10)
                    .padding(.bottom, 4)

                QuickActionsGrid()
                    .frame(maxHeight: 300)
            }

            Divider()

            // Footer Actions
            HStack {
                Button("Refresh") {
                    Task {
                        await refreshAll()
                    }
                }
                .buttonStyle(.bordered)
                .keyboardShortcut("r", modifiers: [.command, .shift])

                Text("Cmd+Shift+J to toggle")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .controlSize(.small)

                Spacer()

                Button("Quit") {
                    NSApplication.shared.terminate(nil)
                }
                .buttonStyle(.bordered)
                .tint(.red)
                .keyboardShortcut("q", modifiers: [.command])
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
        }
        .onAppear {
            webSocket.connect()
            // Request notification authorization safely
            Task {
                await NotificationManager.shared.requestAuthorization()
            }
            // Install global hotkey handler
            MenuBarManager.shared.installHotKeyHandler()
        }
        .onDrop(of: [.fileURL], isTargeted: $showDropOverlay) { providers in
            handleDroppedFiles(providers: providers)
            return true
        }
        .overlay {
            if showDropOverlay {
                ZStack {
                    Color.blue.opacity(0.1)
                    VStack(spacing: 16) {
                        Image(systemName: "arrow.down.doc")
                            .font(.system(size: 48))
                        Text("Drop files to analyze")
                            .font(.headline)
                    }
                }
                .transition(.opacity)
            }
        }
        .animation(.easeInOut(duration: 0.2), value: showDropOverlay)
    }

    // MARK: - Actions

    private func refreshAll() async {
        try? await webSocket.sendWithoutResponse(action: "get_status", data: nil)
        try? await webSocket.sendWithoutResponse(action: "get_containers", data: nil)
    }

    private func handleDroppedFiles(providers: [NSItemProvider]) {
        Task { @MainActor in
            for provider in providers {
                guard provider.hasItemConformingToTypeIdentifier(UTType.fileURL.identifier) else {
                    continue
                }

                _ = provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier) { item, error in
                    guard let data = item as? Data,
                          let url = URL(dataRepresentation: data, relativeTo: nil) else {
                        return
                    }

                    // Send file to Jarvis via WebSocket
                    Task { @MainActor in
                        await processDroppedFile(url)
                    }
                }
            }

            // Hide overlay after a delay
            try? await Task.sleep(nanoseconds: 500_000_000)
            showDropOverlay = false
        }
    }

    private func processDroppedFile(_ url: URL) async {
        // Determine file type and send appropriate command
        let fileExtension = url.pathExtension.lowercased()

        var action: String
        var data: [String: Any]

        switch fileExtension {
        case "py", "swift", "js", "ts":
            action = "analyze_code"
            data = ["file_path": url.path]
        case "txt", "md":
            action = "read_file"
            data = ["file_path": url.path]
        default:
            action = "process_file"
            data = ["file_path": url.path]
        }

        do {
            try await webSocket.sendWithoutResponse(action: action, data: data)
        } catch {
            ErrorHandler.shared.handle(error, context: "processDroppedFile")
        }
    }
}
