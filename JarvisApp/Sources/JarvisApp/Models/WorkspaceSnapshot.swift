import Foundation

struct WorkspaceSnapshotResponse: Codable {
    let workspaceRoot: String
    let runtimeConfig: RuntimeConfig
    let summary: WorkspaceSummary
    let worktrees: [WorkspaceWorktree]
    let containers: [WorkspaceContainer]
    let taskExecutions: [WorkspaceTaskExecution]?
    let recentEvents: [WorkspaceTraceEvent]?

    enum CodingKeys: String, CodingKey {
        case workspaceRoot = "workspace_root"
        case runtimeConfig = "runtime_config"
        case summary
        case worktrees
        case containers
        case taskExecutions = "task_executions"
        case recentEvents = "recent_events"
    }
}

struct RuntimeConfig: Codable {
    let providerType: String?
    let modelExecutor: String?
    let workspaceRootConfig: String?
    let a2aWorkflowMode: String?
    let a2aOpencodeModel: String?
    let taskTimeoutSecs: String?
    let opencodeTimeoutSecs: String?

    enum CodingKeys: String, CodingKey {
        case providerType = "provider_type"
        case modelExecutor = "model_executor"
        case workspaceRootConfig = "workspace_root_config"
        case a2aWorkflowMode = "a2a_workflow_mode"
        case a2aOpencodeModel = "a2a_opencode_model"
        case taskTimeoutSecs = "task_timeout_secs"
        case opencodeTimeoutSecs = "opencode_timeout_secs"
    }
}

struct WorkspaceSummary: Codable {
    let worktreeCount: Int
    let containerCount: Int
    let mappedContainerCount: Int
    let generatedAt: String?

    enum CodingKeys: String, CodingKey {
        case worktreeCount = "worktree_count"
        case containerCount = "container_count"
        case mappedContainerCount = "mapped_container_count"
        case generatedAt = "generated_at"
    }
}

struct WorkspaceWorktree: Identifiable, Codable {
    let id: String
    let path: String
}

struct WorkspaceContainer: Identifiable, Codable {
    let id: String
    let name: String
    let status: String
    let image: String
    let cpus: Int?
    let memory: String?
    let taskId: String?
    let mountPaths: [String]
    let worktreePath: String?

    enum CodingKeys: String, CodingKey {
        case id, name, status, image, cpus, memory
        case taskId = "task_id"
        case mountPaths = "mount_paths"
        case worktreePath = "worktree_path"
    }
}

struct WorkspaceTaskExecution: Identifiable, Codable {
    let taskId: String
    let description: String
    let status: String
    let providerType: String
    let modelId: String
    let workflow: String
    let workflowReason: String?
    let updatedAt: Double?

    var id: String { taskId }

    enum CodingKeys: String, CodingKey {
        case taskId = "task_id"
        case description
        case status
        case providerType = "provider_type"
        case modelId = "model_id"
        case workflow
        case workflowReason = "workflow_reason"
        case updatedAt = "updated_at"
    }
}

struct WorkspaceTraceEvent: Identifiable, Codable {
    let id: String
    let timestamp: Double
    let eventType: String
    let summary: String
    let taskId: String?
    let metadata: [String: String]?

    enum CodingKeys: String, CodingKey {
        case id
        case timestamp
        case eventType = "event_type"
        case summary
        case taskId = "task_id"
        case metadata
    }
}
