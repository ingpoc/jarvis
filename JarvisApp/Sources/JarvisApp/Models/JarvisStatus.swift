import SwiftUI

enum JarvisStatus: String, Codable {
    case idle
    case building
    case testing
    case error
    case waitingApproval = "waiting_approval"

    var color: Color {
        switch self {
        case .idle: .green
        case .building: .blue
        case .testing: .yellow
        case .error: .red
        case .waitingApproval: .orange
        }
    }

    var label: String {
        switch self {
        case .idle: "Idle"
        case .building: "Building"
        case .testing: "Testing"
        case .error: "Error"
        case .waitingApproval: "Waiting Approval"
        }
    }

    var iconName: String { "brain.head.profile" }
}

struct JarvisStatusResponse: Codable {
    let status: JarvisStatus
    let currentSession: String?
    let currentFeature: String?
    let uptime: Double?

    enum CodingKeys: String, CodingKey {
        case status
        case currentSession = "current_session"
        case currentFeature = "current_feature"
        case uptime
    }
}
