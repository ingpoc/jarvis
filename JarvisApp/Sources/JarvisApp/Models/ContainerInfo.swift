import SwiftUI

struct ContainerInfo: Identifiable, Codable {
    let id: String
    let name: String
    let status: String
    let image: String
    let cpus: Int?
    let memory: String?
    let taskId: String?

    var statusColor: Color {
        switch status.lowercased() {
        case "running": .green
        case "stopped", "exited": .red
        case "paused": .yellow
        default: .secondary
        }
    }

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

    var statusColor: Color {
        switch status.lowercased() {
        case "running", "in_progress": .blue
        case "completed", "success": .green
        case "failed", "error": .red
        case "pending", "queued": .yellow
        default: .secondary
        }
    }

    var progressValue: Double {
        Double(percentComplete ?? 0) / 100.0
    }

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
