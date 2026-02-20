import Foundation

struct WorkspaceSnapshotResponse: Codable {
    let workspaceRoot: String
    let runtimeConfig: RuntimeConfig
    let summary: WorkspaceSummary
    let paths: WorkspacePaths?
    let worktrees: [WorkspaceWorktree]
    let containers: [WorkspaceContainer]
    let taskExecutions: [WorkspaceTaskExecution]?
    let recentEvents: [WorkspaceTraceEvent]?

    enum CodingKeys: String, CodingKey {
        case workspaceRoot = "workspace_root"
        case runtimeConfig = "runtime_config"
        case summary
        case paths
        case worktrees
        case containers
        case taskExecutions = "task_executions"
        case recentEvents = "recent_events"
    }
}

struct WorkspacePaths: Codable {
    let jarvisHome: String?
    let systemDir: String?
    let jarvisConfig: String?
    let opencodeConfig: String?
    let runtimeWorkflowDir: String?
    let runtimeDocsDir: String?
    let runtimeMcpConfig: String?
    let a2aToken: String?
    let logsDir: String?
    let dbPath: String?
    let pidsDir: String?

    enum CodingKeys: String, CodingKey {
        case jarvisHome = "jarvis_home"
        case systemDir = "system_dir"
        case jarvisConfig = "jarvis_config"
        case opencodeConfig = "opencode_config"
        case runtimeWorkflowDir = "runtime_workflow_dir"
        case runtimeDocsDir = "runtime_docs_dir"
        case runtimeMcpConfig = "runtime_mcp_config"
        case a2aToken = "a2a_token"
        case logsDir = "logs_dir"
        case dbPath = "db_path"
        case pidsDir = "pids_dir"
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
    let delegatedProviderPolicy: String?
    let delegatedPermissionMode: String?
    let opencodeSessionPermissionProfile: String?
    let opencodeSessionPermissionsCount: Int?
    let mcpConfigSource: String?
    let loadedStaticMcpServers: [String]
    let loadedDynamicMcpServers: [String]
    let capabilityToolCount: Int?
    let capabilityMcpToolCount: Int?
    let capabilityAgents: [String]
    let capabilityHooks: [String]
    let capabilitySkills: [String]
    let skillsEnabled: Bool?
    let skillToolAvailable: Bool?
    let discoveredSkillCount: Int?
    let discoveredSkillsPreview: [String]
    let discoveredSkills: [String]
    let discoveredMcpServers: [String]

    enum CodingKeys: String, CodingKey {
        case providerType = "provider_type"
        case modelExecutor = "model_executor"
        case workspaceRootConfig = "workspace_root_config"
        case a2aWorkflowMode = "a2a_workflow_mode"
        case a2aOpencodeModel = "a2a_opencode_model"
        case taskTimeoutSecs = "task_timeout_secs"
        case opencodeTimeoutSecs = "opencode_timeout_secs"
        case delegatedProviderPolicy = "delegated_provider_policy"
        case delegatedPermissionMode = "delegated_permission_mode"
        case opencodeSessionPermissionProfile = "opencode_session_permission_profile"
        case opencodeSessionPermissionsCount = "opencode_session_permissions_count"
        case mcpConfigSource = "mcp_config_source"
        case loadedStaticMcpServers = "loaded_static_mcp_servers"
        case loadedDynamicMcpServers = "loaded_dynamic_mcp_servers"
        case capabilityToolCount = "capability_tool_count"
        case capabilityMcpToolCount = "capability_mcp_tool_count"
        case capabilityAgents = "capability_agents"
        case capabilityHooks = "capability_hooks"
        case capabilitySkills = "capability_skills"
        case skillsEnabled = "skills_enabled"
        case skillToolAvailable = "skill_tool_available"
        case discoveredSkillCount = "discovered_skill_count"
        case discoveredSkillsPreview = "discovered_skills_preview"
        case discoveredSkills = "discovered_skills"
        case discoveredMcpServers = "discovered_mcp_servers"
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
