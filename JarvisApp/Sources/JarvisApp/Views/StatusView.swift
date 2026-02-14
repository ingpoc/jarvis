import SwiftUI

/// Enhanced Timeline View with cleaner design
/// Design: Legible typography, clear visual hierarchy, peaceful colors
struct TimelineView: View {
    @State private var wsClient = WebSocketClient(
        serverURL: URL(string: "wss://localhost:9848")!
    )

    @State private var filter: EventFilterType = .all

    var body: some View {
        VStack(spacing: 0) {
            // Filter Bar
            FilterBar(selected: $filter) { newFilter in
                filter = newFilter
            }

            Divider()

            // Events List
            ScrollView {
                LazyVStack(spacing: 0) {
                    ForEach(filteredEvents) { event in
                        EventRow(event: event)
                        Divider().padding(.leading, 60)
                    }
                }
            }
        }
        .onAppear {
            wsClient.connect()
        }
        .onDisappear {
            wsClient.disconnect()
        }
    }

    private var filteredEvents: [TimelineEvent] {
        switch filter {
        case .all:
            return wsClient.events
        case .errors:
            return wsClient.events.filter { $0.eventType == "error" }
        case .approvals:
            return wsClient.events.filter { $0.eventType == "approval_needed" }
        case .tasks:
            return wsClient.events.filter { $0.eventType.hasPrefix("task_") }
        }
    }
}

// MARK: - Filter Types

enum EventFilterType: String, CaseIterable {
    case all = "All"
    case errors = "Errors"
    case approvals = "Approvals"
    case tasks = "Tasks"

    var icon: String {
        switch self {
        case .all: return "line.3.horizontal.decrease.circle"
        case .errors: return "xmark.circle"
        case .approvals: return "checkmark.circle"
        case .tasks: return "checklist"
        }
    }
}

// MARK: - Filter Bar

struct FilterBar: View {
    @Binding var selected: EventFilterType
    let onFilterChange: (EventFilterType) -> Void

    var body: some View {
        HStack(spacing: 4) {
            ForEach(EventFilterType.allCases, id: \.self) { filter in
                FilterButton(
                    filter: filter,
                    isSelected: selected == filter
                ) {
                    selected = filter
                    onFilterChange(filter)
                }
            }
            Spacer()
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(Color(nsColor: .controlBackgroundColor))
    }
}

struct FilterButton: View {
    let filter: EventFilterType
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 6) {
                Image(systemName: filter.icon)
                    .font(.system(size: 11))

                Text(filter.rawValue)
                    .font(.system(size: 12, weight: isSelected ? .semibold : .regular))
            }
            .foregroundStyle(isSelected ? .white : .secondary)
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .background(isSelected ? Color.accentColor : Color.clear)
            .cornerRadius(5)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Event Row

struct EventRow: View {
    let event: TimelineEvent

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            // Icon
            eventIcon
                .frame(width: 24, height: 24)

            // Content
            VStack(alignment: .leading, spacing: 4) {
                Text(event.summary)
                    .font(.system(size: 13))
                    .foregroundStyle(.primary)
                    .lineLimit(2)

                HStack(spacing: 8) {
                    Text(event.timeString)
                        .font(.system(size: 11))
                        .foregroundStyle(.tertiary)

                    if let cost = event.costUsd, cost > 0 {
                        Text("•")
                            .foregroundStyle(.tertiary)

                        Text("$\(String(format: "%.2f", cost))")
                            .font(.system(size: 11))
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .padding(.vertical, 12)

            Spacer()
        }
        .padding(.horizontal, 16)
        .background(Color(nsColor: .textBackgroundColor))
    }

    private var eventIcon: some View {
        ZStack {
            Circle()
                .fill(iconColor.opacity(0.15))
                .frame(width: 24, height: 24)

            Image(systemName: iconName)
                .font(.system(size: 10, weight: .medium))
                .foregroundStyle(iconColor)
        }
    }

    private var iconName: String {
        switch event.eventType {
        case "error": return "xmark"
        case "approval_needed": return "hand.raised"
        case "task_start": return "play.circle"
        case "task_complete": return "checkmark"
        case "feature_start": return "sparkles"
        case "feature_complete": return "checkmark.circle"
        case "tool_use": return "wrench.and.screwdriver"
        default: return "circle"
        }
    }

    private var iconColor: Color {
        switch event.eventType {
        case "error": return .red
        case "approval_needed": return .orange
        case "task_start": return .blue
        case "task_complete": return .green
        case "feature_complete": return .green
        default: return .secondary
        }
    }
}
