//
//  TimelineView.swift
//  JarvisiOSApp
//
//  Touch-friendly event timeline with pull-to-refresh
//

import SwiftUI

struct TimelineView: View {
    @State private var events: [TimelineEvent] = [
        TimelineEvent(id: 1, type: .task, title: "Feature completed", message: "User authentication flow", time: Date().addingTimeInterval(-300)),
        TimelineEvent(id: 2, type: .approval, title: "Approval needed", message: "Deploy to production", time: Date().addingTimeInterval(-600)),
        TimelineEvent(id: 3, type: .error, title: "Build failed", message: "Tests not passing", time: Date().addingTimeInterval(-900)),
    ]

    var body: some View {
        NavigationView {
            List {
                ForEach(events) { event in
                    EventRow(event: event)
                    .listRowSeparator(.hidden)
                }
            }
            .listStyle(.plain)
            .navigationTitle("Timeline")
            .refreshable {
                await refreshEvents()
            }
        }
    }

    private func refreshEvents() async {
        try? await Task.sleep(nanoseconds: 500_000_000)
    }
}

struct TimelineEvent: Identifiable {
    let id: Int
    let type: EventType
    let title: String
    let message: String
    let time: Date
}

enum EventType {
    case task
    case approval
    case error
    case info

    var color: Color {
        switch self {
        case .task: return .blue
        case .approval: return .orange
        case .error: return .red
        case .info: return .gray
        }
    }

    var icon: String {
        switch self {
        case .task: return "checkmark.circle"
        case .approval: return "hand.raised"
        case .error: return "xmark.circle"
        case .info: return "info.circle"
        }
    }
}

struct EventRow: View {
    let event: TimelineEvent

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: event.type.icon)
                .font(.title3)
                .foregroundStyle(event.type.color)
                .frame(width: 28)

            VStack(alignment: .leading, spacing: 4) {
                Text(event.title)
                    .font(.headline)

                Text(event.message)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)

                Text(event.time, style: .relative)
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            }
        }
        .padding(.vertical, 4)
    }
}

#Preview {
    TimelineView()
}
