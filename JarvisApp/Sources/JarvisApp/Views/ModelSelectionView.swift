import SwiftUI

// MARK: - Model Info

struct ModelInfo: Identifiable {
    let id: String
    let name: String
    let provider: ModelProvider
    let description: String
    var isAvailable: Bool
    var isSelected: Bool
}

enum ModelProvider: String, CaseIterable {
    case anthropic = "Anthropic Claude"
    case glm = "GLM (z.ai)"
    case lmstudio = "LM Studio (Local)"
    case mlx = "MLX (Apple Silicon)"
    case foundation = "Foundation Models"
    
    var icon: String {
        switch self {
        case .anthropic: return "brain"
        case .glm: return "cpu"
        case .lmstudio: return "laptopcomputer"
        case .mlx: return "memorychip"
        case .foundation: return "apple.logo"
        }
    }
}

// MARK: - Model Selection View

struct ModelSelectionView: View {
    @Environment(\.webSocket) private var webSocket
    @State private var selectedModelId: String = "claude-sonnet-4-5-20250929"
    @State private var currentProvider: String = "anthropic"
    @State private var isLoading = false
    @State private var lmstudioModels: [String] = []
    @State private var lmstudioRunning = false
    @State private var lmstudioModelLoaded: String?
    @State private var mlxAvailable = false
    @State private var foundationAvailable = true  // Default to true - AFM available on macOS 26+
    
    private var modelStatus: ModelStatusInfo? {
        webSocket.modelStatus
    }
    
    private var models: [ModelInfo] {
        var allModels: [ModelInfo] = []
        
        // Anthropic models - always available
        allModels.append(ModelInfo(
            id: "claude-sonnet-4-5-20250929",
            name: "Claude Sonnet 4.5",
            provider: .anthropic,
            description: "Best balance of speed and capability",
            isAvailable: true,
            isSelected: selectedModelId == "claude-sonnet-4-5-20250929"
        ))
        allModels.append(ModelInfo(
            id: "claude-opus-4-6",
            name: "Claude Opus 4.6",
            provider: .anthropic,
            description: "Most capable model for complex tasks",
            isAvailable: true,
            isSelected: selectedModelId == "claude-opus-4-6"
        ))
        allModels.append(ModelInfo(
            id: "claude-haiku-4-5-20251001",
            name: "Claude Haiku 4.5",
            provider: .anthropic,
            description: "Fast responses for simple tasks",
            isAvailable: true,
            isSelected: selectedModelId == "claude-haiku-4-5-20251001"
        ))
        
        // LM Studio models
        let lmModels = modelStatus?.lmstudioAvailableModels ?? lmstudioModels
        let lmRunning = modelStatus?.lmstudioRunning ?? lmstudioRunning
        let lmLoaded = modelStatus?.lmstudioModelLoaded ?? lmstudioModelLoaded
        
        if !lmModels.isEmpty {
            for modelId in lmModels {
                let displayName = modelId
                    .replacingOccurrences(of: "lmstudio-community/", with: "")
                    .replacingOccurrences(of: "qwen2.5-coder-3b-instruct-mlx", with: "Qwen2.5 Coder 3B")
                    .replacingOccurrences(of: "openai/gpt-oss-20b", with: "GPT-OSS 20B")
                    .replacingOccurrences(of: "deepseek/deepseek-r1-0528-qwen3-8b", with: "DeepSeek R1 8B")
                
                allModels.append(ModelInfo(
                    id: modelId,
                    name: "\(displayName) (LM Studio)",
                    provider: .lmstudio,
                    description: lmRunning ? (lmLoaded == modelId ? "● Loaded" : "Click to load") : "Click to start LM Studio",
                    isAvailable: true,
                    isSelected: selectedModelId == modelId
                ))
            }
        }
        
        // MLX models - hide for now since not implemented
        // if mlxAvailable {
        //     allModels.append(ModelInfo(
        //         id: "mlx-qwen3-3b",
        //         name: "Qwen3 3B (MLX)",
        //         provider: .mlx,
        //         description: "On-device inference via MLX",
        //         isAvailable: true,
        //         isSelected: selectedModelId == "mlx-qwen3-3b"
        //     ))
        // }
        
        // Foundation Models - always available on macOS 26+
        if foundationAvailable {
            allModels.append(ModelInfo(
                id: "foundation-models",
                name: "Foundation Models",
                provider: .foundation,
                description: currentProvider == "foundation" ? "● Active (direct Python)" : "Apple on-device AI (~1s)",
                isAvailable: true,
                isSelected: selectedModelId == "foundation-models"
            ))
        }
        
        // GLM - unavailable
        allModels.append(ModelInfo(
            id: "glm-5",
            name: "GLM-5 (z.ai)",
            provider: .glm,
            description: "Subscription expired",
            isAvailable: false,
            isSelected: selectedModelId == "glm-5"
        ))
        
        return allModels
    }
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                // Header
                VStack(alignment: .leading, spacing: 4) {
                    Text("Model Selection")
                        .font(.headline)
                    Text("Choose the AI model that powers Jarvis")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .padding(.horizontal, 16)
                .padding(.top, 12)
                
                // Provider sections
                ForEach(ModelProvider.allCases, id: \.self) { provider in
                    let providerModels = models.filter { $0.provider == provider }
                    if !providerModels.isEmpty {
                        providerSection(provider: provider, models: providerModels)
                    }
                }
                
                // Error banner
                if let error = webSocket.lastError, error.contains("expire") || error.contains("subscription") {
                    errorBanner(message: error)
                }
            }
            .padding(.vertical, 8)
        }
        .onAppear {
            webSocket.sendCommand(action: "get_model_status")
            checkLocalModels()
        }
    }
    
    private func checkLocalModels() {
        // Directly check Foundation Models availability via Python
        DispatchQueue.global().async {
            let task = Process()
            task.executableURL = URL(fileURLWithPath: "/Users/gurusharan/Documents/remote-claude/Codex/jarvis-mac/.venv/bin/python")
            task.arguments = ["-c", "import sys; sys.path.insert(0, '/Users/gurusharan/Documents/remote-claude/Codex/jarvis-mac/src'); from jarvis.afm_integration import is_afm_available; print('available' if is_afm_available() else 'unavailable')"]
            task.currentDirectoryURL = URL(fileURLWithPath: "/Users/gurusharan/Documents/remote-claude/Codex/jarvis-mac")
            
            let pipe = Pipe()
            task.standardOutput = pipe
            task.standardError = pipe
            
            do {
                try task.run()
                task.waitUntilExit()
                
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                let output = String(data: data, encoding: .utf8) ?? ""
                
                DispatchQueue.main.async {
                    self.foundationAvailable = output.contains("available")
                    print("Foundation Models check: \(output.trimmingCharacters(in: .whitespacesAndNewlines))")
                }
            } catch {
                print("Error checking Foundation: \(error)")
            }
        }
        
        // Also request model status from daemon
        webSocket.sendCommand(action: "get_model_status")
    }
    
    private func providerSection(provider: ModelProvider, models: [ModelInfo]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: provider.icon)
                    .foregroundStyle(providerColor(provider))
                Text(provider.rawValue)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                Spacer()
            }
            .padding(.horizontal, 16)
            
            ForEach(models) { model in
                modelRow(model: model)
            }
        }
    }
    
    private func modelRow(model: ModelInfo) -> some View {
        Button(action: {
            if model.isAvailable {
                selectedModelId = model.id
                switchModel(model.id)
            }
        }) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    HStack {
                        Text(model.name)
                            .font(.subheadline)
                            .fontWeight(.medium)
                        
                        if selectedModelId == model.id {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundStyle(.blue)
                                .font(.caption)
                        }
                    }
                    
                    Text(model.description)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                
                Spacer()
                
                if !model.isAvailable {
                    Label("Unavailable", systemImage: "exclamationmark.triangle.fill")
                        .font(.caption)
                        .foregroundStyle(.orange)
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(
                RoundedRectangle(cornerRadius: 8)
                    .fill(selectedModelId == model.id ? Color.blue.opacity(0.1) : Color.clear)
            )
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(!model.isAvailable)
        .opacity(model.isAvailable ? 1.0 : 0.5)
    }
    
    private func errorBanner(message: String) -> some View {
        HStack {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(.orange)
            Text(message)
                .font(.caption)
                .lineLimit(2)
            Spacer()
            Button("Retry") {
                webSocket.sendCommand(action: "get_status")
            }
            .font(.caption)
            .buttonStyle(.bordered)
        }
        .padding(12)
        .background(Color.orange.opacity(0.1))
        .cornerRadius(8)
        .padding(.horizontal, 16)
    }
    
    private func providerColor(_ provider: ModelProvider) -> Color {
        switch provider {
        case .anthropic: return .purple
        case .glm: return .blue
        case .lmstudio: return .green
        case .mlx: return .cyan
        case .foundation: return .red
        }
    }
    
    private func switchModel(_ modelId: String) {
        isLoading = true
        webSocket.sendCommand(action: "switch_model", data: ["model": modelId])
        
        DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
            isLoading = false
        }
    }
}
