import SwiftUI
import JarvisClient

@available(iOS 17, *)
struct PairingView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(AuthManager.self) private var auth

    @State private var step = PairingStep.deviceName
    @State private var deviceName = ""
    @State private var pairingToken: String?
    @State private var qrData: String?
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showSuccess = false

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                // Progress indicator
                ProgressHeader(currentStep: step)

                Divider()

                // Content based on current step
                Group {
                    switch step {
                    case .deviceName:
                        DeviceNameStep(
                            deviceName: $deviceName,
                            isLoading: isLoading,
                            onNext: initiatePairing
                        )
                    case .scanQR:
                        QRScanStep(
                            qrData: qrData,
                            isLoading: isLoading,
                            onConfirm: confirmPairing
                        )
                    case .complete:
                        CompletionStep(
                            deviceName: deviceName,
                            onDismiss: { dismiss() }
                        )
                    }
                }

                Spacer()
            }
            .padding()
            .navigationTitle("Pair Device")
            .optionalNavigationBarTitleDisplayMode()
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
            .alert("Pairing Error", isPresented: .constant(errorMessage != nil)) {
                Button("OK") { errorMessage = nil }
            } message: {
                Text(errorMessage ?? "")
            }
        }
    }

    // MARK: - Pairing Logic

    private func initiatePairing() {
        guard !deviceName.isEmpty else { return }

        isLoading = true
        errorMessage = nil

        Task {
            do {
                let response = try await auth.initiatePairing(deviceName: deviceName)
                await MainActor.run {
                    pairingToken = response.token
                    qrData = response.qrData
                    step = .scanQR
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    isLoading = false
                }
            }
        }
    }

    private func confirmPairing() {
        guard let token = pairingToken else { return }

        isLoading = true
        errorMessage = nil

        Task {
            do {
                try await auth.confirmPairing(token: token)
                await MainActor.run {
                    step = .complete
                    isLoading = false
                    showSuccess = true
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    isLoading = false
                }
            }
        }
    }
}

// MARK: - Pairing Step Enum

enum PairingStep: Equatable {
    case deviceName
    case scanQR
    case complete
}

// MARK: - Progress Header

struct ProgressHeader: View {
    let currentStep: PairingStep

    private var stepIndex: Int {
        switch currentStep {
        case .deviceName: return 0
        case .scanQR: return 1
        case .complete: return 2
        }
    }

    var body: some View {
        HStack(spacing: 8) {
            ForEach(0..<3) { index in
                if index > 0 {
                    Rectangle()
                        .fill(index < stepIndex ? Color.accentColor : Color.gray.opacity(0.3))
                        .frame(height: 2)
                        .animation(.easeInOut, value: stepIndex)
                }

                Circle()
                    .fill(index <= stepIndex ? Color.accentColor : Color.gray.opacity(0.3))
                    .frame(width: 24, height: 24)
                    .overlay {
                        Text("\(index + 1)")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundStyle(index <= stepIndex ? .white : .secondary)
                    }
                    .animation(.easeInOut, value: stepIndex)
            }
        }
        .padding(.vertical, 8)
    }
}

// MARK: - Device Name Step

struct DeviceNameStep: View {
    @Binding var deviceName: String
    let isLoading: Bool
    let onNext: () -> Void

    var body: some View {
        VStack(spacing: 24) {
            VStack(spacing: 8) {
                Image(systemName: "iphone")
                    .font(.system(size: 48))
                    .foregroundStyle(accentColor)

                Text("Name Your Device")
                    .font(.system(size: 20, weight: .semibold))

                Text("Choose a name to identify this device")
                    .font(.system(size: 14))
                    .foregroundStyle(.secondary)
            }

            VStack(spacing: 16) {
                TextField("Device Name", text: $deviceName)
                    .textFieldStyle(.roundedBorder)
                    .autocapitalization(.words)
                    .disableAutocorrection(true)

                Text("This name will appear in your device list")
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)
            }

            Button(action: onNext) {
                HStack {
                    if isLoading {
                        ProgressView()
                            .progressViewStyle(.circular)
                            .tint(.white)
                    }
                    Text("Continue")
                }
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.primaryButtonStyle())
            .disabled(deviceName.isEmpty || isLoading)
        }
    }
}

// MARK: - QR Scan Step

struct QRScanStep: View {
    let qrData: String?
    let isLoading: Bool
    let onConfirm: () -> Void

    var body: some View {
        VStack(spacing: 24) {
            VStack(spacing: 8) {
                Image(systemName: "qrcode.viewfinder")
                    .font(.system(size: 48))
                    .foregroundStyle(accentColor)

                Text("Scan QR Code")
                    .font(.system(size: 20, weight: .semibold))

                Text("Scan this code with your paired device")
                    .font(.system(size: 14))
                    .foregroundStyle(.secondary)
            }

            VStack(spacing: 16) {
                if let qrData = qrData {
                    QRCodeView(data: qrData)
                        .frame(width: 200, height: 200)
                } else {
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color.gray.opacity(0.2))
                        .frame(width: 200, height: 200)
                        .overlay {
                            ProgressView()
                        }
                }

                VStack(spacing: 8) {
                    Text("Waiting for device confirmation...")
                        .font(.system(size: 14))
                        .foregroundStyle(.secondary)

                    Text("The code will expire in 5 minutes")
                        .font(.system(size: 12))
                        .foregroundStyle(.secondary)
                }
            }

            Button(action: onConfirm) {
                HStack {
                    if isLoading {
                        ProgressView()
                            .progressViewStyle(.circular)
                            .tint(.white)
                    }
                    Text("I've Scanned the Code")
                }
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.primaryButtonStyle())
            .disabled(qrData == nil || isLoading)
        }
    }
}

// MARK: - Completion Step

struct CompletionStep: View {
    let deviceName: String
    let onDismiss: () -> Void

    var body: some View {
        VStack(spacing: 24) {
            VStack(spacing: 8) {
                ZStack {
                    Circle()
                        .fill(Color.green.opacity(0.15))
                        .frame(width: 80, height: 80)

                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 48))
                        .foregroundStyle(.green)
                }

                Text("Pairing Complete")
                    .font(.system(size: 20, weight: .semibold))

                Text("\"\(deviceName)\" has been successfully paired")
                    .font(.system(size: 14))
                    .foregroundStyle(.secondary)
            }

            VStack(spacing: 12) {
                Label("Access granted to Jarvis", systemImage: "checkmark")
                Label("Commands enabled", systemImage: "checkmark")
                Label("Real-time updates active", systemImage: "checkmark")
            }
            .font(.system(size: 14))
            .foregroundStyle(.secondary)

            Button(action: onDismiss) {
                Text("Done")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.primaryButtonStyle())
        }
    }
}

// MARK: - QR Code View

struct QRCodeView: View {
    let data: String

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 12)
                .fill(Color.white)
                .shadow(radius: 4)

            Image(platformImage: generateQRCode(from: data))
                .interpolation(.none)
                .resizable()
                .scaledToFit()
                .padding(8)
        }
    }

    private func generateQRCode(from string: String) -> PlatformImage {
        #if os(iOS)
        let data = string.data(using: .utf8)

        filter = CIFilter(name: "CIQRCodeGenerator")
        filter?.setValue(data, forKey: "inputMessage")

        let scale = UIScreen.main.scale

        if let outputImage = filter?.outputImage {
            let transform = CGAffineTransform(scaleX: scale, y: scale)
            let scaledImage = outputImage.transformed(by: transform)

            if let cgImage = CIContext().createCGImage(scaledImage, from: scaledImage.extent) {
                return UIImage(cgImage: cgImage)
            }
        }

        return UIImage()
        #else
        return NSImage()
        #endif
    }

    private var filter: CIFilter?
}

// MARK: - Button Styles

struct PrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 16, weight: .semibold))
            .foregroundStyle(.white)
            .padding(.horizontal, 24)
            .padding(.vertical, 14)
            .frame(maxWidth: .infinity)
            .background(Color.accentColor)
            .cornerRadius(12)
            .opacity(configuration.isPressed ? 0.8 : 1.0)
    }
}

extension ButtonStyle where Self == PrimaryButtonStyle {
    static func primaryButtonStyle() -> PrimaryButtonStyle {
        PrimaryButtonStyle()
    }
}

// MARK: - Preview

#Preview {
    PairingView()
        .environment(AuthManager.shared)
}
