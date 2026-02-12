import SwiftUI

enum CommandCenterTab: String, CaseIterable {
    case containers = "Containers"
    case tools = "Tools"
    case tasks = "Tasks"
}

struct CommandCenterView: View {
    @Environment(WebSocketClient.self) private var ws
    @State private var selectedTab: CommandCenterTab = .containers

    var body: some View {
        VStack(spacing: 0) {
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
            case .tools:
                AvailableToolsView(tools: ws.availableTools)
            case .tasks:
                TaskProgressView(tasks: ws.activeTasks)
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
        }
    }
}

struct ContainerListView: View {
    let containers: [ContainerInfo]

    var body: some View {
        Group {
            if containers.isEmpty {
                Text("No containers running")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 200)
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
        .frame(maxHeight: 320)
    }
}

struct AvailableToolsView: View {
    let tools: [String]

    var body: some View {
        Group {
            if tools.isEmpty {
                Text("No tools discovered yet")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 200)
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
        .frame(maxHeight: 320)
    }
}

struct TaskProgressView: View {
    let tasks: [TaskProgress]

    var body: some View {
        Group {
            if tasks.isEmpty {
                Text("No active tasks")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 200)
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
        .frame(maxHeight: 320)
    }
}
