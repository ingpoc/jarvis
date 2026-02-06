import Foundation

struct TimelineEvent: Identifiable, Codable {
    let id: Int?
    let timestamp: Double
    let eventType: String
    let summary: String
    let sessionId: String?
    let taskId: String?
    let featureId: String?
    let costUsd: Double?

    var date: Date { Date(timeIntervalSince1970: timestamp) }

    var timeString: String {
        let fmt = DateFormatter()
        fmt.dateFormat = "HH:mm:ss"
        return fmt.string(from: date)
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
