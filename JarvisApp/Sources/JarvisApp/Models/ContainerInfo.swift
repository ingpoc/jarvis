import Foundation

struct ContainerInfo: Identifiable, Codable {
    let id: String
    let name: String
    let status: String
    let image: String
    let cpus: Int?
    let memory: String?
    let taskId: String?

    var displayName: String {
        name.isEmpty ? id : name
    }

    enum CodingKeys: String, CodingKey {
        case id, name, status, image, cpus, memory
        case taskId = "task_id"
    }
}

struct TaskProgress: Identifiable, Codable {
    let taskId: String
    let description: String
    let status: String
    let currentStep: String?
    let percentComplete: Int?
    let costUsd: Double

    var id: String { taskId }

    enum CodingKeys: String, CodingKey {
        case taskId = "task_id"
        case description, status
        case currentStep = "current_step"
        case percentComplete = "percent_complete"
        case costUsd = "cost_usd"
    }
}

struct ContainersResponse: Codable {
    let containers: [ContainerInfo]
}
