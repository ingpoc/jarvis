import SwiftUI

enum JarvisStatus: String, Codable {
    case idle
    case building
    case testing
    case reviewing
    case error
    case completed
    case waitingApproval = "waiting_approval"

    var color: Color {
        switch self {
        case .idle: .gray
        case .building: .blue
        case .testing: .yellow
        case .reviewing: .purple
        case .error: .red
        case .completed: .green
        case .waitingApproval: .orange
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
        }
    }
}

struct JarvisStatusResponse: Codable {
    let status: JarvisStatus
    let currentSession: String?
    let currentFeature: String?
    let uptime: Double?
    let trust: TrustInfo?
    let budget: BudgetInfo?

    enum CodingKeys: String, CodingKey {
        case status
        case currentSession = "current_session"
        case currentFeature = "current_feature"
        case uptime
        case trust
        case budget
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
