import Foundation

public struct TimelineEvent: Identifiable, Codable, Sendable {
    public let id: Int?
    public let timestamp: Double
    public let eventType: String
    public let summary: String
    public let sessionId: String?
    public let taskId: String?
    public let featureId: String?
    public let costUsd: Double?

    public var date: Date { Date(timeIntervalSince1970: timestamp) }

    public var timeString: String {
        let fmt = DateFormatter()
        fmt.dateFormat = "HH:mm:ss"
        return fmt.string(from: date)
    }

    public init(
        id: Int? = nil,
        timestamp: Double,
        eventType: String,
        summary: String,
        sessionId: String? = nil,
        taskId: String? = nil,
        featureId: String? = nil,
        costUsd: Double? = nil
    ) {
        self.id = id
        self.timestamp = timestamp
        self.eventType = eventType
        self.summary = summary
        self.sessionId = sessionId
        self.taskId = taskId
        self.featureId = featureId
        self.costUsd = costUsd
    }

    enum CodingKeys: String, CodingKey {
        case id, timestamp, summary
        case eventType = "event_type"
        case sessionId = "session_id"
        case taskId = "task_id"
        case featureId = "feature_id"
        case costUsd = "cost_usd"
    }
}
