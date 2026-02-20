import SwiftUI

enum CommandCenterTab: String, CaseIterable {
    case containers = "Containers"
    case workspace = "Workspace"
    case traces = "Traces"
    case tools = "Tools"
}

struct CommandCenterView: View {
    @Environment(WebSocketClient.self) private var ws
    @State private var selectedTab: CommandCenterTab = .containers

    var body: some View {
        VStack(spacing: 0) {
            CommandCenterSummaryHeader(snapshot: ws.workspaceSnapshot, containerCount: ws.containers.count)
                .padding(.horizontal, 16)
                .padding(.vertical, 10)

            Divider()

            Picker("Tab", selection: $selectedTab) {
                ForEach(CommandCenterTab.allCases, id: \.self) { tab in
                    Text(tab.rawValue).tag(tab)
                }
            }
            .pickerStyle(.segmented)
            .padding(.horizontal, 16)
            .padding(.vertical, 12)

            Divider()

            switch selectedTab {
            case .containers:
                ContainerListView(containers: ws.containers)
            case .workspace:
                WorkspaceSnapshotView(snapshot: ws.workspaceSnapshot)
            case .traces:
                TraceListView(events: ws.workspaceSnapshot?.recentEvents ?? [])
            case .tools:
                AvailableToolsView(tools: ws.availableTools)
            }

            Divider()

            HStack {
                Button("Refresh") {
                    Task {
                        await ws.refreshContainers()
                    }
                    ws.sendCommand(action: "get_status")
                    ws.sendCommand(action: "get_timeline")
                    ws.sendCommand(action: "get_available_tools")
                    ws.sendCommand(action: "get_workspace_snapshot")
                }
                .buttonStyle(.bordered)
                .disabled(ws.isLoading)

                if ws.isLoading {
                    ProgressView()
                        .controlSize(.small)
                }

                Spacer()

                if let error = ws.lastError {
                    HStack(spacing: 4) {
                        Image(systemName: "exclamationmark.triangle.fill")
                        Text(error)
                            .font(.caption2)
                    }
                    .foregroundStyle(.red)
                    .font(.caption)
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
        }
        .onAppear {
            Task {
                await ws.refreshContainers()
            }
            ws.sendCommand(action: "get_workspace_snapshot")
        }
    }
}

private struct CommandCenterSummaryHeader: View {
    let snapshot: WorkspaceSnapshotResponse?
    let containerCount: Int

    var body: some View {
        HStack(spacing: 14) {
            SummaryPill(
                title: "Worktrees",
                value: "\(snapshot?.summary.worktreeCount ?? 0)"
            )
            SummaryPill(
                title: "Containers",
                value: "\(snapshot?.summary.containerCount ?? containerCount)"
            )
            SummaryPill(
                title: "Provider",
                value: snapshot?.runtimeConfig.providerType ?? "unknown"
            )
            SummaryPill(
                title: "Workflow",
                value: snapshot?.runtimeConfig.a2aWorkflowMode ?? "auto"
            )
            Spacer()
        }
    }
}

private struct SummaryPill: View {
    let title: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title)
                .font(.caption2)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.caption)
                .fontWeight(.semibold)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 7)
        .background(Color.secondary.opacity(0.12))
        .cornerRadius(8)
    }
}

struct ContainerListView: View {
    let containers: [ContainerInfo]

    var body: some View {
        Group {
            if containers.isEmpty {
                Text("No containers running")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 340)
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 8) {
                        ForEach(containers) { container in
                            HStack(spacing: 12) {
                                Image(systemName: container.statusIcon)
                                    .foregroundStyle(container.statusColor)
                                    .font(.caption)

                                VStack(alignment: .leading, spacing: 2) {
                                    Text(container.displayName)
                                        .font(.caption)
                                        .fontWeight(.medium)

                                    Text(container.image)
                                        .font(.caption2)
                                        .foregroundStyle(.secondary)

                                    if let cpus = container.cpus, let memory = container.memory {
                                        HStack(spacing: 4) {
                                            Image(systemName: "cpu.fill")
                                            Text("\(cpus)")
                                            Text("·")
                                            Image(systemName: "memorychip.fill")
                                            Text(memory)
                                        }
                                        .font(.caption2)
                                        .foregroundStyle(.secondary)
                                    }
                                }

                                Spacer()
                            }
                            .padding(.horizontal, 16)
                            .padding(.vertical, 6)
                            .accessibilityElement(children: .combine)
                            .accessibilityLabel(container.displayName)
                            .accessibilityValue("\(container.status), \(container.image)")
                        }
                    }
                    .padding(.vertical, 8)
                }
            }
        }
        .frame(maxHeight: .infinity)
    }
}

struct WorkspaceSnapshotView: View {
    let snapshot: WorkspaceSnapshotResponse?

    var body: some View {
        Group {
            if let snapshot {
                ScrollView {
                    VStack(alignment: .leading, spacing: 12) {
                        WorkspaceSection(
                            title: "Runtime Config",
                            rows: [
                                ("Provider", snapshot.runtimeConfig.providerType ?? "unknown"),
                                ("Model", snapshot.runtimeConfig.modelExecutor ?? "unknown"),
                                ("Workflow Mode", snapshot.runtimeConfig.a2aWorkflowMode ?? "auto"),
                                ("A2A OpenCode Model", snapshot.runtimeConfig.a2aOpencodeModel ?? "unknown"),
                                ("Task Timeout (s)", nonEmpty(snapshot.runtimeConfig.taskTimeoutSecs)),
                                ("OpenCode Timeout (s)", nonEmpty(snapshot.runtimeConfig.opencodeTimeoutSecs)),
                            ]
                        )
                        WorkspaceSection(
                            title: "Workspace",
                            rows: [
                                ("Workspace Root", snapshot.workspaceRoot),
                                ("Configured Root", snapshot.runtimeConfig.workspaceRootConfig ?? "unset"),
                                ("Worktrees", "\(snapshot.summary.worktreeCount)"),
                                ("Containers", "\(snapshot.summary.containerCount)"),
                                ("Mapped Containers", "\(snapshot.summary.mappedContainerCount)"),
                            ]
                        )

                        Divider()

                        Text("Task Execution Config")
                            .font(.caption)
                            .fontWeight(.semibold)
                            .foregroundStyle(.secondary)
                            .padding(.horizontal, 16)

                        if let taskRows = snapshot.taskExecutions, !taskRows.isEmpty {
                            ForEach(taskRows) { row in
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(row.taskId)
                                        .font(.caption2)
                                        .foregroundStyle(.secondary)
                                    Text(row.description)
                                        .font(.caption)
                                        .fontWeight(.medium)
                                        .lineLimit(2)
                                    Text("status=\(row.status) workflow=\(row.workflow) provider=\(row.providerType)")
                                        .font(.caption2)
                                        .foregroundStyle(.secondary)
                                        .lineLimit(1)
                                    Text(row.modelId)
                                        .font(.caption2)
                                        .foregroundStyle(.tertiary)
                                        .lineLimit(1)
                                }
                                .padding(.horizontal, 16)
                                .padding(.vertical, 5)
                            }
                        } else {
                            Text("No recent task execution metadata")
                                .foregroundStyle(.secondary)
                                .padding(.horizontal, 16)
                                .padding(.vertical, 6)
                        }

                        Divider()

                        Text("Container ↔ Worktree")
                            .font(.caption)
                            .fontWeight(.semibold)
                            .foregroundStyle(.secondary)
                            .padding(.horizontal, 16)

                        if snapshot.containers.isEmpty {
                            Text("No Jarvis containers found")
                                .foregroundStyle(.secondary)
                                .padding(.horizontal, 16)
                                .padding(.vertical, 6)
                        } else {
                            ForEach(snapshot.containers) { container in
                                VStack(alignment: .leading, spacing: 4) {
                                    HStack {
                                        Text(container.name.isEmpty ? container.id : container.name)
                                            .font(.caption)
                                            .fontWeight(.medium)
                                        Spacer()
                                        Text(container.status)
                                            .font(.caption2)
                                            .foregroundStyle(.secondary)
                                    }
                                    Text("Worktree: \(container.worktreePath ?? "unmapped")")
                                        .font(.caption2)
                                        .foregroundStyle(container.worktreePath == nil ? .orange : .secondary)
                                    if !container.mountPaths.isEmpty {
                                        Text("Mounts: \(container.mountPaths.joined(separator: ", "))")
                                            .font(.caption2)
                                            .foregroundStyle(.secondary)
                                            .lineLimit(2)
                                    }
                                }
                                .padding(.horizontal, 16)
                                .padding(.vertical, 6)
                            }
                        }

                        Divider()

                        Text("Discovered Worktrees")
                            .font(.caption)
                            .fontWeight(.semibold)
                            .foregroundStyle(.secondary)
                            .padding(.horizontal, 16)

                        if snapshot.worktrees.isEmpty {
                            Text("No git worktrees discovered under workspace")
                                .foregroundStyle(.secondary)
                                .padding(.horizontal, 16)
                                .padding(.vertical, 6)
                        } else {
                            ForEach(snapshot.worktrees) { worktree in
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(worktree.id)
                                        .font(.caption)
                                        .fontWeight(.medium)
                                    Text(worktree.path)
                                        .font(.caption2)
                                        .foregroundStyle(.secondary)
                                        .lineLimit(2)
                                }
                                .padding(.horizontal, 16)
                                .padding(.vertical, 5)
                            }
                        }
                    }
                    .padding(.vertical, 8)
                }
            } else {
                Text("Workspace snapshot not available yet")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 340)
            }
        }
        .frame(maxHeight: .infinity)
    }

    private func nonEmpty(_ value: String?) -> String {
        if let value, !value.isEmpty {
            return value
        }
        return "unbounded"
    }

}

struct TraceListView: View {
    let events: [WorkspaceTraceEvent]

    var body: some View {
        Group {
            if events.isEmpty {
                Text("No trace events captured yet")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 340)
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 8) {
                        ForEach(Array(events.reversed())) { event in
                            VStack(alignment: .leading, spacing: 3) {
                                HStack {
                                    Text(event.eventType)
                                        .font(.caption2)
                                        .foregroundStyle(.secondary)
                                    Spacer()
                                    Text(timeLabel(event.timestamp))
                                        .font(.caption2)
                                        .foregroundStyle(.tertiary)
                                }
                                Text(event.summary)
                                    .font(.caption)
                                    .lineLimit(3)
                                if let taskId = event.taskId, !taskId.isEmpty {
                                    Text(taskId)
                                        .font(.caption2)
                                        .foregroundStyle(.tertiary)
                                }
                            }
                            .padding(.horizontal, 16)
                            .padding(.vertical, 6)
                        }
                    }
                    .padding(.vertical, 8)
                }
            }
        }
        .frame(maxHeight: .infinity)
    }

    private func timeLabel(_ ts: Double) -> String {
        guard ts > 0 else { return "--:--:--" }
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm:ss"
        return formatter.string(from: Date(timeIntervalSince1970: ts))
    }
}

private struct WorkspaceSection: View {
    let title: String
    let rows: [(String, String)]

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.caption)
                .fontWeight(.semibold)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 16)

            ForEach(rows, id: \.0) { row in
                HStack(alignment: .top) {
                    Text(row.0)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Spacer(minLength: 8)
                    Text(row.1)
                        .font(.caption2)
                        .multilineTextAlignment(.trailing)
                }
                .padding(.horizontal, 16)
            }
        }
    }
}

struct AvailableToolsView: View {
    let tools: [String]

    var body: some View {
        Group {
            if tools.isEmpty {
                Text("No tools discovered yet")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 340)
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 6) {
                        ForEach(Array(tools.prefix(200)), id: \.self) { tool in
                            HStack(alignment: .center, spacing: 8) {
                                Image(systemName: "wrench.and.screwdriver")
                                    .font(.caption2)
                                    .foregroundStyle(.blue)

                                Text(tool)
                                    .font(.caption)
                                    .lineLimit(1)
                            }
                            .padding(.horizontal, 16)
                            .accessibilityElement(children: .combine)
                            .accessibilityLabel("Available tool")
                            .accessibilityValue(tool)
                        }
                    }
                    .padding(.vertical, 6)
                }
            }
        }
        .frame(maxHeight: .infinity)
    }
}

struct TaskProgressView: View {
    let tasks: [TaskProgress]

    var body: some View {
        Group {
            if tasks.isEmpty {
                Text("No active tasks")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 340)
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 10) {
                        ForEach(tasks) { task in
                            VStack(alignment: .leading, spacing: 4) {
                                HStack {
                                    Text(task.description)
                                        .font(.caption)
                                        .fontWeight(.medium)
                                        .lineLimit(1)

                                    Spacer()

                                    Text(String(format: "$%.4f", task.costUsd))
                                        .font(.caption2)
                                        .foregroundStyle(.secondary)
                                }

                                if let step = task.currentStep {
                                    Text(step)
                                        .font(.caption2)
                                        .foregroundStyle(.secondary)
                                }

                                ProgressView(value: task.progressValue)
                                    .progressViewStyle(.linear)
                                    .tint(task.statusColor)

                                HStack {
                                    Image(systemName: task.statusIcon)
                                        .foregroundStyle(task.statusColor)
                                        .font(.caption2)

                                    Text(task.status)
                                        .font(.caption2)
                                        .foregroundStyle(task.statusColor)

                                    Spacer()

                                    if let percent = task.percentComplete {
                                        Text("\(percent)%")
                                            .font(.caption2)
                                            .foregroundStyle(.secondary)
                                    }
                                }
                            }
                            .padding(.horizontal, 16)
                            .padding(.vertical, 8)
                            .background(Color.secondary.opacity(0.1))
                            .cornerRadius(6)
                            .accessibilityElement(children: .combine)
                            .accessibilityLabel("Task: \(task.description)")
                            .accessibilityValue("\(task.status), \(task.percentComplete ?? 0)% complete")
                        }
                    }
                    .padding(.vertical, 8)
                }
            }
        }
        .frame(maxHeight: .infinity)
    }
}
