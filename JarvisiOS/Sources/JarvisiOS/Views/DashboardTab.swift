import SwiftUI
import JarvisClient

struct DashboardTab: View {
    @State private var client = JarvisWebSocketClient.shared

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    StatusCard(status: client.status)
                        .padding(.horizontal)

                    QuickActionsGrid()
                        .padding(.horizontal)

                    RecentActivityPreview(events: client.events)
                        .padding(.horizontal)
                }
                .padding(.vertical)
            }
            .background(Color(PlatformColor.systemGroupedBackground))
        }
        .onAppear { client.connect() }
        .onDisappear { client.disconnect() }
    }
}

struct StatusCard: View {
    let status: JarvisStatus

    var body: some View {
        HStack(spacing: 16) {
            ZStack {
                Circle()
                    .fill(status.color.opacity(0.15))
                    .frame(width: 60, height: 60)

                Circle()
                    .fill(status.color)
                    .frame(width: 16, height: 16)
            }

            VStack(alignment: .leading, spacing: 4) {
                Text(status.label)
                    .font(.system(size: 20, weight: .semibold))

                Text(statusMessage)
                    .font(.system(size: 14))
                    .foregroundStyle(.secondary)
            }

            Spacer()
        }
        .padding()
        .background(Color(PlatformColor.secondarySystemGroupedBackground))
        .cornerRadius(12)
    }

    private var statusMessage: String {
        switch status {
        case .idle: return "Ready for commands"
        case .building: return "Building project..."
        case .testing: return "Running tests..."
        case .error: return "Error occurred"
        case .waitingApproval: return "Awaiting approval"
        }
    }
}

struct QuickActionsGrid: View {
    let actions = [
        (icon: "testtube.2", title: "Test", color: Color.blue),
        (icon: "hammer", title: "Build", color: Color.orange),
        (icon: "sparkles", title: "Clean", color: Color.purple),
        (icon: "branch", title: "Git", color: Color.green),
    ]

    var body: some View {
        LazyVGrid(columns: [
            GridItem(.flexible(), spacing: 12),
            GridItem(.flexible(), spacing: 12),
        ], spacing: 12) {
            ForEach(actions, id: \.title) { action in
                QuickActionButton(
                    icon: action.icon,
                    title: action.title,
                    color: action.color
                )
            }
        }
    }
}

struct QuickActionButton: View {
    let icon: String
    let title: String
    let color: Color

    var body: some View {
        Button(action: {
            #if os(iOS)
            let generator = UIImpactFeedbackGenerator(style: .light)
            generator.impactOccurred()
            #endif
        }) {
            VStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.system(size: 24))

                Text(title)
                    .font(.system(size: 12, weight: .medium))
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 20)
            .background(Color(PlatformColor.secondarySystemGroupedBackground))
            .foregroundStyle(color)
            .cornerRadius(10)
        }
        .buttonStyle(.plain)
    }
}

struct RecentActivityPreview: View {
    let events: [TimelineEvent]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Recent Activity")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(.secondary)
                .padding(.horizontal, 4)

            VStack(spacing: 0) {
                ForEach(Array(events.prefix(3).enumerated()), id: \.element.id) { index, event in
                    EventRow(event: event)
                    if index < min(events.count, 3) - 1 {
                        Divider().padding(.leading, 44)
                    }
                }
            }
            .background(Color(PlatformColor.secondarySystemGroupedBackground))
            .cornerRadius(10)
        }
    }
}

struct EventRow: View {
    let event: TimelineEvent

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: iconName)
                .font(.system(size: 12))
                .foregroundStyle(iconColor)
                .frame(width: 20)

            Text(event.summary)
                .font(.system(size: 13))
                .lineLimit(1)

            Spacer()

            Text(event.timeString)
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
    }

    private var iconName: String {
        switch event.eventType {
        case "error": return "xmark.circle"
        case "approval_needed": return "hand.raised"
        case "task_complete": return "checkmark.circle"
        default: return "circle"
        }
    }

    private var iconColor: Color {
        switch event.eventType {
        case "error": return .red
        case "approval_needed": return .orange
        case "task_complete": return .green
        default: return .secondary
        }
    }
}
