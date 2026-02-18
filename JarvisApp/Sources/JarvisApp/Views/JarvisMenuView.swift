import SwiftUI
import UniformTypeIdentifiers

// MARK: - Menu View Options

enum MenuView: String, CaseIterable, Identifiable {
    case timeline = "Timeline"
    case commandCenter = "Command Center"
    case quickActions = "Quick Actions"
    case models = "Models"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .timeline: return "clock.arrow.circlepath"
        case .commandCenter: return "chart.bar.doc.horizontal"
        case .quickActions: return "bolt.circle"
        case .models: return "cpu"
        }
    }
}

// MARK: - Menu View

struct JarvisMenuView: View {
    @Environment(\.webSocket) private var webSocket
    @Environment(\.openWindow) private var openWindow
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

            // Idle notification banner
            if webSocket.status.isIdle && webSocket.idleInfo != nil {
                IdleNotificationBanner(status: webSocket.status, idleInfo: webSocket.idleInfo!)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 6)

                Divider()
            }

            // Command input
            CommandInputView()
                .padding(.horizontal, 16)
                .padding(.vertical, 8)

            Divider()

            // Pending approvals section
            if !webSocket.pendingApprovals.isEmpty {
                HStack {
                    Text("Pending Approvals")
                        .font(.headline)
                    Spacer()
                    Text("\(webSocket.pendingApprovals.count)")
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

            // Content
            Group {
                switch selectedView {
                case .timeline:
                    TimelineView()
                case .commandCenter:
                    CommandCenterView()
                case .quickActions:
                    QuickActionsGrid()
                case .models:
                    ModelSelectionView()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

            Divider()

            // Bottom bar
            HStack {
                Button(action: {
                    webSocket.sendCommand(action: "get_status")
                    webSocket.sendCommand(action: "get_timeline")
                }) {
                    Label("Refresh", systemImage: "arrow.clockwise")
                }
                .buttonStyle(.bordered)
                .controlSize(.small)

                Spacer()

                Button(action: {
                    openWindow(id: "full-app")
                }) {
                    Label("Open", systemImage: "arrow.up.right.square")
                }
                .buttonStyle(.bordered)
                .controlSize(.small)

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

                do {
                    let item = try await provider.loadItem(
                        forTypeIdentifier: UTType.fileURL.identifier
                    )

                    let resolvedURL: URL?
                    if let url = item as? URL {
                        resolvedURL = url
                    } else if let nsurl = item as? NSURL {
                        resolvedURL = nsurl as URL
                    } else if let data = item as? Data {
                        resolvedURL = URL(dataRepresentation: data, relativeTo: nil)
                    } else if let str = item as? String {
                        resolvedURL = URL(string: str)
                    } else if let nsstr = item as? NSString {
                        resolvedURL = URL(string: nsstr as String)
                    } else {
                        resolvedURL = nil
                    }

                    guard let url = resolvedURL else { continue }
                    await processDroppedFile(url)
                } catch {
                    ErrorHandler.shared.handle(error, context: "handleDroppedFiles")
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
        .frame(width: 200)
    }
}

// MARK: - Idle Notification Banner

struct IdleNotificationBanner: View {
    let status: JarvisStatus
    let idleInfo: IdleInfo

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: status.iconName)
                .font(.caption)
                .foregroundStyle(status.color)

            VStack(alignment: .leading, spacing: 2) {
                Text(status.label)
                    .font(.caption)
                    .fontWeight(.medium)

                if let taskCount = idleInfo.backgroundTasks, taskCount > 0 {
                    Text("\(taskCount) background task\(taskCount == 1 ? "" : "s") running")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                } else if status == .hibernated {
                    Text("System hibernated — memory pressure detected")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                } else {
                    Text("No pending work — monitoring for changes")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()

            // Idle state indicator dot
            Circle()
                .fill(status.color)
                .frame(width: 8, height: 8)
                .opacity(status == .idleProcessing ? 1.0 : 0.5)
        }
        .padding(8)
        .background(status.color.opacity(0.08))
        .cornerRadius(8)
    }
}
