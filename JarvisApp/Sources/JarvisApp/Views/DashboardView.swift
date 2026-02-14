import SwiftUI

/// Dashboard: At-a-glance status and quick actions
/// Design: Clear hierarchy, essential info only, calm color palette
struct DashboardView: View {
    @Environment(NavigationRouter.self) private var router

    var body: some View {
        ScrollView {
            VStack(spacing: 32) {
                // Status Card
                StatusCard()

                // Quick Actions
                QuickActionsGrid()

                // Recent Activity Preview
                RecentActivityCard()

                Spacer()
            }
            .padding(32)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(nsColor: .textBackgroundColor))
    }
}

// MARK: - Status Card

struct StatusCard: View {
    @Environment(NavigationRouter.self) private var router

    var body: some View {
        HStack(spacing: 24) {
            // Status Indicator
            ZStack {
                Circle()
                    .fill(router.currentStatus.color.opacity(0.15))
                    .frame(width: 80, height: 80)

                Circle()
                    .fill(router.currentStatus.color)
                    .frame(width: 24, height: 24)
                    .glow(radius: 8)
            }

            VStack(alignment: .leading, spacing: 6) {
                Text("Jarvis is \(router.currentStatus.label.lowercased())")
                    .font(.system(size: 20, weight: .semibold))
                    .foregroundStyle(.primary)

                Text(statusMessage)
                    .font(.system(size: 13))
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }

            Spacer()
        }
        .padding(24)
        .background(Color(nsColor: .controlBackgroundColor))
        .cornerRadius(12)
    }

    private var statusMessage: String {
        switch router.currentStatus {
        case .idle: return "Ready for new tasks"
        case .building: return "Compiling and building..."
        case .testing: return "Running test suite..."
        case .error: return "An error occurred"
        case .waitingApproval: return "Awaiting your approval"
        }
    }
}

// MARK: - Quick Actions Grid

struct QuickActionsGrid: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Quick Actions")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(.secondary)
                .padding(.horizontal, 4)

            LazyVGrid(columns: [
                GridItem(.flexible(), spacing: 12),
                GridItem(.flexible(), spacing: 12),
            ], spacing: 12) {
                QuickActionButton(
                    title: "Run Tests",
                    icon: "testtube.2",
                    color: .blue
                )

                QuickActionButton(
                    title: "Build Project",
                    icon: "hammer",
                    color: .orange
                )

                QuickActionButton(
                    title: "Clean Build",
                    icon: "sparkles",
                    color: .purple
                )

                QuickActionButton(
                    title: "Git Status",
                    icon: "branch",
                    color: .green
                )
            }
        }
    }
}

struct QuickActionButton: View {
    let title: String
    let icon: String
    let color: Color

    var body: some View {
        Button(action: {}) {
            VStack(spacing: 12) {
                Image(systemName: icon)
                    .font(.system(size: 20))
                    .foregroundStyle(color)

                Text(title)
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(.primary)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 20)
            .background(Color(nsColor: .controlBackgroundColor))
            .cornerRadius(8)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Recent Activity Card

struct RecentActivityCard: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Recent Activity")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(.secondary)
                .padding(.horizontal, 4)

            VStack(spacing: 0) {
                ActivityRow(
                    icon: "checkmark.circle.fill",
                    color: .green,
                    title: "Tests passed",
                    time: "2m ago"
                )

                Divider().padding(.leading, 44)

                ActivityRow(
                    icon: "hammer.fill",
                    color: .blue,
                    title: "Build completed",
                    time: "5m ago"
                )

                Divider().padding(.leading, 44)

                ActivityRow(
                    icon: "figure.walk",
                    color: .orange,
                    title: "Awaiting approval",
                    time: "12m ago"
                )
            }
            .background(Color(nsColor: .controlBackgroundColor))
            .cornerRadius(8)
        }
    }
}

struct ActivityRow: View {
    let icon: String
    let color: Color
    let title: String
    let time: String

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 14))
                .foregroundStyle(color)
                .frame(width: 20)

            Text(title)
                .font(.system(size: 13))
                .foregroundStyle(.primary)

            Spacer()

            Text(time)
                .font(.system(size: 11))
                .foregroundStyle(.tertiary)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
    }
}
