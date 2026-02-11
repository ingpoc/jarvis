import SwiftUI

// MARK: - ContainerInfo Extensions
extension ContainerInfo {
    var statusColor: Color {
        switch status.lowercased() {
        case "running": .green
        case "stopped", "exited": .red
        case "paused": .yellow
        default: .secondary
        }
    }

    var statusIcon: String {
        switch status.lowercased() {
        case "running": return "checkmark.circle.fill"
        case "stopped", "exited": return "xmark.circle.fill"
        case "paused": return "pause.circle.fill"
        default: return "questionmark.circle.fill"
        }
    }
}

// MARK: - TaskProgress Extensions
extension TaskProgress {
    var statusColor: Color {
        switch status.lowercased() {
        case "running", "in_progress": .blue
        case "completed", "success": .green
        case "failed", "error": .red
        case "pending", "queued": .yellow
        default: .secondary
        }
    }

    var statusIcon: String {
        switch status.lowercased() {
        case "running", "in_progress": return "arrow.triangle.2.circlepath"
        case "completed", "success": return "checkmark.circle.fill"
        case "failed", "error": return "xmark.circle.fill"
        case "pending", "queued": return "clock.fill"
        default: return "circle.fill"
        }
    }

    var progressValue: Double {
        Double(percentComplete ?? 0) / 100.0
    }
}

// MARK: - JarvisStatus Extensions
extension JarvisStatus {
    var color: Color {
        switch self {
        case .idle: .green
        case .building: .blue
        case .testing: .yellow
        case .error: .red
        case .waitingApproval: .orange
        }
    }

    var iconName: String { "brain.head.profile" }
}

// MARK: - Event Colors Utility
struct EventColors {
    static func color(for eventType: String) -> Color {
        switch eventType {
        case "tool_use": .blue
        case "approval_needed": .orange
        case "error", "failure": .red
        case "success", "complete": .green
        case "build_start", "build_end": .blue
        case "test_start", "test_end": .yellow
        default: .primary
        }
    }
}
