import SwiftUI

struct TimelineView: View {
    @Environment(WebSocketClient.self) private var ws
    @State private var selectedFilter: EventFilter = .all
    @State private var selectedEvent: TimelineEvent?

    var body: some View {
        VStack(spacing: 0) {
            // Event filter bar
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    ForEach(EventFilter.allCases) { filter in
                        FilterChip(
                            label: filter.label,
                            isSelected: selectedFilter == filter,
                            color: filter.color
                        ) {
                            selectedFilter = filter
                        }
                    }
                }
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
            }

            Divider()

            // Events list
            let visible = filteredEvents
            if visible.isEmpty {
                Text(selectedFilter == .all ? "No events yet" : "No \(selectedFilter.label.lowercased()) events")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 60)
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 2) {
                        ForEach(visible) { event in
                            EventRow(event: event, isSelected: selectedEvent?.id == event.id)
                                .onTapGesture {
                                    withAnimation(.easeInOut(duration: 0.15)) {
                                        selectedEvent = selectedEvent?.id == event.id ? nil : event
                                    }
                                }

                            // Detail panel when selected
                            if selectedEvent?.id == event.id {
                                EventDetailView(event: event)
                                    .transition(.opacity.combined(with: .move(edge: .top)))
                            }
                        }
                    }
                    .padding(.vertical, 4)
                }
            }
        }
    }

    private var filteredEvents: [TimelineEvent] {
        let all = Array(ws.events.prefix(50))
        switch selectedFilter {
        case .all:
            return all
        case .errors:
            return all.filter { $0.eventType == "error" || $0.eventType == "failure" }
        case .approvals:
            return all.filter { $0.eventType == "approval_needed" || $0.eventType == "approval_granted" || $0.eventType == "approval_denied" }
        case .builds:
            return all.filter { $0.eventType.contains("build") || $0.eventType.contains("test") }
        case .tasks:
            return all.filter { $0.eventType.contains("task") }
        }
    }
}

// MARK: - Event Filter

enum EventFilter: String, CaseIterable, Identifiable {
    case all
    case errors
    case approvals
    case builds
    case tasks

    var id: String { rawValue }

    var label: String {
        switch self {
        case .all: "All"
        case .errors: "Errors"
        case .approvals: "Approvals"
        case .builds: "Builds"
        case .tasks: "Tasks"
        }
    }

    var color: Color {
        switch self {
        case .all: .primary
        case .errors: .red
        case .approvals: .orange
        case .builds: .blue
        case .tasks: .green
        }
    }
}

// MARK: - Filter Chip

struct FilterChip: View {
    let label: String
    let isSelected: Bool
    let color: Color
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(label)
                .font(.caption2)
                .fontWeight(isSelected ? .bold : .regular)
                .padding(.horizontal, 8)
                .padding(.vertical, 3)
                .background(isSelected ? color.opacity(0.2) : .clear)
                .foregroundStyle(isSelected ? color : .secondary)
                .cornerRadius(10)
                .overlay(
                    RoundedRectangle(cornerRadius: 10)
                        .stroke(isSelected ? color.opacity(0.5) : .clear, lineWidth: 1)
                )
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Event Row

struct EventRow: View {
    let event: TimelineEvent
    let isSelected: Bool

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Text(event.timeString)
                .font(.system(.caption, design: .monospaced))
                .foregroundStyle(.secondary)
                .frame(width: 58, alignment: .leading)

            Circle()
                .fill(colorForType(event.eventType))
                .frame(width: 6, height: 6)
                .padding(.top, 4)

            Text(event.eventType)
                .font(.caption)
                .fontWeight(.semibold)
                .foregroundStyle(colorForType(event.eventType))
                .frame(width: 76, alignment: .leading)

            Text(event.summary)
                .font(.caption)
                .lineLimit(isSelected ? nil : 1)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 3)
        .background(isSelected ? Color.accentColor.opacity(0.05) : .clear)
    }

    private func colorForType(_ type: String) -> Color {
        switch type {
        case "approval_needed": .orange
        case "error", "failure": .red
        case "success", "complete", "task_complete": .green
        case "build_start", "build_end": .blue
        case "test_start", "test_end": .yellow
        case "task_start": .cyan
        case "idle_enter", "idle_exit": .gray
        default: .primary
        }
    }
}

// MARK: - Event Detail View

struct EventDetailView: View {
    let event: TimelineEvent

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            if let taskId = event.taskId {
                HStack {
                    Text("Task:")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Text(taskId)
                        .font(.system(.caption2, design: .monospaced))
                }
            }

            if let costUsd = event.costUsd, costUsd > 0 {
                HStack {
                    Text("Cost:")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Text(String(format: "$%.4f", costUsd))
                        .font(.system(.caption2, design: .monospaced))
                }
            }

            HStack {
                Text("Time:")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                Text(event.date.formatted(date: .abbreviated, time: .standard))
                    .font(.caption2)
            }
        }
        .padding(.horizontal, 24)
        .padding(.vertical, 4)
        .padding(.leading, 66)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.accentColor.opacity(0.03))
    }
}
