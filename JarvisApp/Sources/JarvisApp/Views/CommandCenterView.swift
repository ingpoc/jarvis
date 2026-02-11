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
                ToolFeedView(events: ws.events)
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
                }
                .buttonStyle(.bordered)

                Spacer()
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
                            HStack {
                                Circle()
                                    .fill(container.statusColor)
                                    .frame(width: 8, height: 8)

                                VStack(alignment: .leading, spacing: 2) {
                                    Text(container.displayName)
                                        .font(.caption)
                                        .fontWeight(.medium)

                                    Text(container.image)
                                        .font(.caption2)
                                        .foregroundStyle(.secondary)

                                    if let cpus = container.cpus, let memory = container.memory {
                                        HStack(spacing: 4) {
                                            Image(systemName: "cpu")
                                            Text("\(cpus)")
                                            Text("•")
                                            Image(systemName: "memorychip")
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
                        }
                    }
                    .padding(.vertical, 8)
                }
            }
        }
        .frame(maxHeight: 320)
    }
}

struct ToolFeedView: View {
    let events: [TimelineEvent]

    private var toolEvents: [TimelineEvent] {
        events.filter { $0.eventType == "tool_use" }
    }

    var body: some View {
        Group {
            if toolEvents.isEmpty {
                Text("No tool activity")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 200)
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 6) {
                        ForEach(Array(toolEvents.prefix(50))) { event in
                            HStack(alignment: .top, spacing: 8) {
                                Text(event.timeString)
                                    .font(.system(.caption, design: .monospaced))
                                    .foregroundStyle(.secondary)
                                    .frame(width: 64, alignment: .leading)

                                Circle()
                                    .fill(colorForType(event.eventType))
                                    .frame(width: 6, height: 6)

                                Text(event.summary)
                                    .font(.caption)
                                    .lineLimit(2)
                            }
                            .padding(.horizontal, 16)
                        }
                    }
                    .padding(.vertical, 6)
                }
            }
        }
        .frame(maxHeight: 320)
    }

    private func colorForType(_ type: String) -> Color {
        switch type {
        case "tool_use": .blue
        case "error", "failure": .red
        case "success", "complete": .green
        default: .secondary
        }
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
                                    Circle()
                                        .fill(task.statusColor)
                                        .frame(width: 6, height: 6)

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
                        }
                    }
                    .padding(.vertical, 8)
                }
            }
        }
        .frame(maxHeight: 320)
    }
}
