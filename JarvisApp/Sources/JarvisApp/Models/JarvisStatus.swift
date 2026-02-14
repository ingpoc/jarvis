import SwiftUI

enum JarvisStatus: String, Codable {
    case idle
    case building
    case testing
    case reviewing
    case error
    case completed
    case waitingApproval = "waiting_approval"
    case idleProcessing = "idle_processing"
    case hibernated

    var color: Color {
        switch self {
        case .idle: .gray
        case .building: .blue
        case .testing: .yellow
        case .reviewing: .purple
        case .error: .red
        case .completed: .green
        case .waitingApproval: .orange
        case .idleProcessing: .teal
        case .hibernated: .indigo
        }
    }

    var label: String {
        switch self {
        case .idle: "Idle"
        case .building: "Building"
        case .testing: "Testing"
        case .reviewing: "Reviewing"
        case .error: "Error"
        case .completed: "Completed"
        case .waitingApproval: "Waiting Approval"
        case .idleProcessing: "Background Tasks"
        case .hibernated: "Hibernated"
        }
    }

    var iconName: String {
        switch self {
        case .idle: "brain.head.profile"
        case .building: "hammer.fill"
        case .testing: "checkmark.circle"
        case .reviewing: "eye.fill"
        case .error: "exclamationmark.triangle.fill"
        case .completed: "checkmark.seal.fill"
        case .waitingApproval: "hand.raised.fill"
        case .idleProcessing: "gearshape.2.fill"
        case .hibernated: "moon.zzz.fill"
        }
    }

    var isIdle: Bool {
        self == .idle || self == .idleProcessing || self == .hibernated
    }
}

struct JarvisStatusResponse: Codable {
    let status: JarvisStatus
    let currentSession: String?
    let currentFeature: String?
    let uptime: Double?
    let trust: TrustInfo?
    let budget: BudgetInfo?
    let idleInfo: IdleInfo?

    enum CodingKeys: String, CodingKey {
        case status
        case currentSession = "current_session"
        case currentFeature = "current_feature"
        case uptime
        case trust
        case budget
        case idleInfo = "idle_info"
    }
}

struct TrustInfo: Codable {
    let tier: Int?
    let tierName: String?

    enum CodingKeys: String, CodingKey {
        case tier
        case tierName = "tier_name"
    }
}

struct BudgetInfo: Codable {
    let session: String?
    let daily: String?
    let turns: String?
}

struct IdleInfo: Codable {
    let state: String?
    let backgroundTasks: Int?
    let lastActivity: Double?

    enum CodingKeys: String, CodingKey {
        case state
        case backgroundTasks = "background_tasks"
        case lastActivity = "last_activity"
    }
}
