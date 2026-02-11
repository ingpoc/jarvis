import Foundation

struct TimelineEvent: Identifiable, Codable {
    let id: String
    let timestamp: Double
    let eventType: String
    let summary: String
    let sessionId: String?
    let taskId: String?
    let featureId: String?
    let costUsd: Double?

    // Memberwise initializer for PersistenceManager
    init(
        id: String,
        timestamp: Double,
        eventType: String,
        summary: String,
        sessionId: String?,
        taskId: String?,
        featureId: String?,
        costUsd: Double?
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

    var date: Date { Date(timeIntervalSince1970: timestamp) }

    private static let timeFormatter: DateFormatter = {
        let fmt = DateFormatter()
        fmt.dateFormat = "HH:mm:ss"
        return fmt
    }()

    var timeString: String {
        Self.timeFormatter.string(from: date)
    }

    enum CodingKeys: String, CodingKey {
        case id, timestamp, summary
        case eventType = "event_type"
        case sessionId = "session_id"
        case taskId = "task_id"
        case featureId = "feature_id"
        case costUsd = "cost_usd"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        // If id exists, use it; otherwise generate from timestamp+type
        if let id = try? container.decode(String.self, forKey: .id) {
            self.id = id
        } else if let intId = try? container.decode(Int.self, forKey: .id) {
            self.id = String(intId)
        } else {
            let timestamp = try container.decode(Double.self, forKey: .timestamp)
            let eventType = try container.decode(String.self, forKey: .eventType)
            self.id = "\(timestamp)-\(eventType)"
        }
        self.timestamp = try container.decode(Double.self, forKey: .timestamp)
        self.eventType = try container.decode(String.self, forKey: .eventType)
        self.summary = try container.decode(String.self, forKey: .summary)
        self.sessionId = try? container.decodeIfPresent(String.self, forKey: .sessionId)
        self.taskId = try? container.decodeIfPresent(String.self, forKey: .taskId)
        self.featureId = try? container.decodeIfPresent(String.self, forKey: .featureId)
        self.costUsd = try? container.decodeIfPresent(Double.self, forKey: .costUsd)
    }
}
