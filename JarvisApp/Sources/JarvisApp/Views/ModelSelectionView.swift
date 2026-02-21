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
    case opencode = "OpenCode (Zen)"
    
    var icon: String {
        switch self {
        case .opencode: return "shippingbox.fill"
        }
    }
}

// MARK: - Model Selection View

struct ModelSelectionView: View {
    @Environment(\.webSocket) private var webSocket
    @State private var selectedModelId: String = "opencode/glm-5-free"
    @State private var currentProvider: String = "opencode"
    @State private var isLoading = false
    
    private var modelStatus: ModelStatusInfo? {
        webSocket.modelStatus
    }
    
    private var models: [ModelInfo] {
        var allModels: [ModelInfo] = []

        // OpenCode free models (Zen)
        let fallbackOpenCodeModels = [
            "minimax-m2.5-free",
            "glm-5-free",
            "kimi-k2.5-free",
            "big-pickle",
        ]
        let openCodeModels = modelStatus?.opencodeAvailableModels ?? fallbackOpenCodeModels
        for model in openCodeModels {
            let id = model.hasPrefix("opencode/") ? model : "opencode/\(model)"
            allModels.append(ModelInfo(
                id: id,
                name: model,
                provider: .opencode,
                description: currentProvider == "opencode" && selectedModelId == id ? "● Active (OpenCode)" : "Free via OpenCode Zen",
                isAvailable: true,
                isSelected: selectedModelId == id
            ))
        }
        
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
            syncFromModelStatus(modelStatus)
            webSocket.sendCommand(action: "get_model_status")
        }
        .onChange(of: modelStatus?.currentModel) { _ in
            syncFromModelStatus(modelStatus)
        }
        .onChange(of: modelStatus?.provider) { _ in
            syncFromModelStatus(modelStatus)
        }
        .onChange(of: modelStatus?.providerType) { _ in
            syncFromModelStatus(modelStatus)
        }
    }
    
    private func syncFromModelStatus(_ status: ModelStatusInfo?) {
        guard let status else { return }

        if let currentModel = status.currentModel, !currentModel.isEmpty {
            selectedModelId = currentModel
        }
        if let provider = status.providerType ?? status.provider, !provider.isEmpty {
            currentProvider = provider
        }
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
                switchModel(model.id)
            }
        }) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    HStack {
                        Image(systemName: model.provider.icon)
                            .foregroundStyle(providerColor(model.provider))
                            .font(.caption)

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
        case .opencode: return .green
        }
    }
    
    private func switchModel(_ modelId: String) {
        isLoading = true
        webSocket.sendCommand(action: "switch_model", data: ["model": modelId])

        // Refresh from daemon so selection reflects actual active model/provider.
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) {
            webSocket.sendCommand(action: "get_model_status")
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
            isLoading = false
            webSocket.sendCommand(action: "get_model_status")
        }
    }
}
