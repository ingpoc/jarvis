import SwiftUI

/// Initial setup wizard for first-time device pairing
/// Design: Friendly, clear steps, minimal anxiety
struct SetupWizardView: View {
    @Environment(AuthManager.self) private var auth
    @Binding var isPresented: Bool

    @State private var step = 1
    @State private var deviceName = ""
    @State private var serverURL = "wss://localhost:9848"
    @State private var pairingToken: String?
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        VStack(spacing: 0) {
            // Progress indicator
            ProgressStepper(currentStep: step, totalSteps: 3)

            Divider()

            // Content
            Group {
                switch step {
                case 1:
                    WelcomeStep(onNext: { step = 2 })
                case 2:
                    ServerConfigStep(
                        serverURL: $serverURL,
                        onNext: {
                            step = 3
                            if let url = URL(string: serverURL) {
                                auth.setServerURL(url)
                            }
                        }
                    )
                case 3:
                    PairingStep(
                        deviceName: $deviceName,
                        token: pairingToken,
                        isLoading: isLoading,
                        errorMessage: errorMessage,
                        onPair: initiatePairing,
                        onComplete: {
                            isPresented = false
                        }
                    )
                default:
                    EmptyView()
                }
            }

            Spacer()
        }
        .frame(width: 500, height: 400)
    }

    private func initiatePairing() {
        guard !deviceName.isEmpty else { return }
        isLoading = true
        errorMessage = nil

        Task {
            do {
                let response = try await auth.initiatePairing(deviceName: deviceName)
                pairingToken = response.token
                // In a real app, you would wait for confirmation
                try await Task.sleep(nanoseconds: 2_000_000_000)
                try await auth.confirmPairing(token: response.token)
            } catch {
                errorMessage = error.localizedDescription
            }
            isLoading = false
        }
    }
}

// MARK: - Progress Stepper

struct ProgressStepper: View {
    let currentStep: Int
    let totalSteps: Int

    var body: some View {
        HStack(spacing: 8) {
            ForEach(1...totalSteps, id: \.self) { step in
                if step < totalSteps {
                    StepIndicator(number: step, isActive: step <= currentStep)
                    Spacer()
                } else {
                    StepIndicator(number: step, isActive: step <= currentStep)
                }
            }
        }
        .padding(24)
    }
}

struct StepIndicator: View {
    let number: Int
    let isActive: Bool

    var body: some View {
        ZStack {
            Circle()
                .fill(isActive ? Color.accentColor : Color.secondary.opacity(0.3))
                .frame(width: 28, height: 28)

            Text("\(number)")
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(isActive ? .white : .secondary)
        }
    }
}

// MARK: - Welcome Step

struct WelcomeStep: View {
    let onNext: () -> Void

    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            Image(systemName: "brain.head.profile")
                .font(.system(size: 48))
                .foregroundStyle(.accentColor)

            VStack(spacing: 8) {
                Text("Welcome to Jarvis")
                    .font(.system(size: 20, weight: .semibold))

                Text("Your autonomous development partner")
                    .font(.system(size: 13))
                    .foregroundStyle(.secondary)
            }

            Spacer()

            VStack(alignment: .leading, spacing: 12) {
                FeatureRow(icon: "checkmark.circle", text: "Real-time project monitoring")
                FeatureRow(icon: "checkmark.circle", text: "Voice command interface")
                FeatureRow(icon: "checkmark.circle", text: "Remote access from anywhere")
            }

            Spacer()

            Button("Get Started") {
                onNext()
            }
            .buttonStyle(.primaryButtonStyle)
        }
        .padding(32)
    }
}

struct FeatureRow: View {
    let icon: String
    let text: String

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .foregroundStyle(.accentColor)
                .frame(width: 16)

            Text(text)
                .font(.system(size: 12))
                .foregroundStyle(.primary)
        }
    }
}

// MARK: - Server Config Step

struct ServerConfigStep: View {
    @Binding var serverURL: String
    let onNext: () -> Void

    var body: some View {
        VStack(spacing: 24) {
            VStack(spacing: 8) {
                Text("Server Connection")
                    .font(.system(size: 16, weight: .semibold))

                Text("Enter your Jarvis server address")
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)
            }

            Spacer()

            VStack(alignment: .leading, spacing: 8) {
                Text("Server URL")
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(.secondary)

                TextField("wss://your-server:9848", text: $serverURL)
                    .textFieldStyle(.roundedBorder)
                    .font(.system(size: 12))
                    .autocapitalization(.never)
                    .disableAutocorrection(true)
            }

            VStack(alignment: .leading, spacing: 6) {
                Text("For local development, use:")
                    .font(.system(size: 10))
                    .foregroundStyle(.tertiary)

                Text("wss://localhost:9848")
                    .font(.system(size: 10, family: .monospaced))
                    .foregroundStyle(.secondary)
            }

            Spacer()

            HStack(spacing: 12) {
                Button("Back") {
                    // Navigate back
                }
                .buttonStyle(.secondaryButtonStyle)

                Button("Continue") {
                    onNext()
                }
                .buttonStyle(.primaryButtonStyle)
                .disabled(serverURL.isEmpty)
            }
        }
        .padding(32)
    }
}

// MARK: - Pairing Step

struct PairingStep: View {
    @Binding var deviceName: String
    let token: String?
    let isLoading: Bool
    let errorMessage: String?
    let onPair: () -> Void
    let onComplete: () -> Void

    var body: some View {
        VStack(spacing: 24) {
            VStack(spacing: 8) {
                Text("Pair This Device")
                    .font(.system(size: 16, weight: .semibold))

                Text("Enter a name for this device")
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)
            }

            Spacer()

            if let error = errorMessage {
                HStack(spacing: 8) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(.red)

                    Text(error)
                        .font(.system(size: 11))
                        .foregroundStyle(.red)
                }
                .padding(12)
                .background(Color.red.opacity(0.1))
                .cornerRadius(6)
            }

            if let token = token {
                VStack(spacing: 16) {
                    QRCodeView(token: token)
                        .frame(width: 180, height: 180)

                    Text("Scan this code on your server to approve")
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)

                    Button("Complete Setup") {
                        onComplete()
                    }
                    .buttonStyle(.primaryButtonStyle)
                }
            } else {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Device Name")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundStyle(.secondary)

                    TextField("My Mac", text: $deviceName)
                        .textFieldStyle(.roundedBorder)
                        .font(.system(size: 12))
                }

                if isLoading {
                    ProgressView()
                        .controlSize(.small)
                }

                Button("Pair Device") {
                    onPair()
                }
                .buttonStyle(.primaryButtonStyle)
                .disabled(deviceName.isEmpty || isLoading)
            }

            Spacer()
        }
        .padding(32)
    }
}
