import Foundation
import SwiftUI

public enum JarvisStatus: String, Codable, Sendable {
    case idle
    case building
    case testing
    case error
    case waitingApproval = "waiting_approval"

    #if canImport(SwiftUI)
    @available(macOS 14, iOS 17, *)
    public var color: Color {
        switch self {
        case .idle: .green
        case .building: .blue
        case .testing: .yellow
        case .error: .red
        case .waitingApproval: .orange
        }
    }
    #endif

    public var label: String {
        switch self {
        case .idle: "Idle"
        case .building: "Building"
        case .testing: "Testing"
        case .error: "Error"
        case .waitingApproval: "Waiting Approval"
        }
    }

    public var iconName: String { "brain.head.profile" }
}

public struct JarvisStatusResponse: Codable, Sendable {
    public let status: JarvisStatus
    public let currentSession: String?
    public let currentFeature: String?
    public let uptime: Double?

    enum CodingKeys: String, CodingKey {
        case status
        case currentSession = "current_session"
        case currentFeature = "current_feature"
        case uptime
    }
}
