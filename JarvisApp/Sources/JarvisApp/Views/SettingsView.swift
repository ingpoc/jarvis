import SwiftUI

/// Settings View: Authentication and device management
/// Design: Clear sections, minimal controls, honest feedback
struct SettingsView: View {
    @Environment(AuthManager.self) private var auth
    @State private var showQRCode = false
    @State private var showDeviceList = false

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // Connection Status
                ConnectionCard()

                // Server Configuration
                ServerConfigCard()

                // Device Management
                DeviceManagementCard()

                // About
                AboutCard()

                Spacer()
            }
            .padding(24)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(nsColor: .textBackgroundColor))
        .sheet(isPresented: $showQRCode) {
            QRCodeView(isPresented: $showQRCode)
        }
        .sheet(isPresented: $showDeviceList) {
            DeviceListView(isPresented: $showDeviceList)
        }
    }
}

// MARK: - Connection Card

struct ConnectionCard: View {
    @Environment(AuthManager.self) private var auth
    @State private var wsClient: WebSocketClient?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Connection")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(.secondary)

            HStack(spacing: 12) {
                ConnectionStatusIndicator(isConnected: wsClient?.isConnected ?? false)

                VStack(alignment: .leading, spacing: 2) {
                    Text(wsClient?.isConnected == true ? "Connected" : "Disconnected")
                        .font(.system(size: 13, weight: .medium))

                    Text(auth.serverURL.host ?? "Unknown")
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                }

                Spacer()

                Button(wsClient?.isConnected == true ? "Disconnect" : "Connect") {
                    if wsClient?.isConnected == true {
                        wsClient?.disconnect()
                    } else {
                        wsClient?.connect()
                    }
                }
                .buttonStyle(.secondaryButtonStyle)
            }
            .padding()
            .background(Color(nsColor: .controlBackgroundColor))
            .cornerRadius(8)
        }
        .onAppear {
            wsClient = WebSocketClient(serverURL: auth.serverURL)
        }
    }
}

struct ConnectionStatusIndicator: View {
    let isConnected: Bool

    var body: some View {
        Circle()
            .fill(isConnected ? .green : .red)
            .frame(width: 8, height: 8)
            .glow(radius: isConnected ? 3 : 0)
    }
}

// MARK: - Server Config Card

struct ServerConfigCard: View {
    @Environment(AuthManager.self) private var auth
    @State private var serverURL: String = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Server Configuration")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(.secondary)

            HStack {
                Image(systemName: "server.rack")
                    .foregroundStyle(.secondary)
                    .frame(width: 20)

                TextField("Server URL", text: $serverURL)
                    .textFieldStyle(.plain)
                    .font(.system(size: 12))

                if !serverURL.isEmpty {
                    Button("Save") {
                        if let url = URL(string: serverURL) {
                            auth.setServerURL(url)
                        }
                    }
                    .buttonStyle(.secondaryButtonStyle)
                }
            }
            .padding()
            .background(Color(nsColor: .controlBackgroundColor))
            .cornerRadius(8)
        }
        .onAppear {
            serverURL = auth.serverURL.absoluteString
        }
    }
}

// MARK: - Device Management Card

struct DeviceManagementCard: View {
    @Environment(AuthManager.self) private var auth
    @State private var showPairingSheet = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("This Device")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(.secondary)

                Spacer()

                Button("Add New Device") {
                    showPairingSheet = true
                }
                .buttonStyle(.secondaryButtonStyle)
            }

            HStack(spacing: 12) {
                Image(systemName: "iphone")
                    .foregroundStyle(.secondary)
                    .frame(width: 20)

                VStack(alignment: .leading, spacing: 2) {
                    Text(auth.currentToken?.deviceName ?? "Unknown Device")
                        .font(.system(size: 12, weight: .medium))

                    Text(auth.currentToken?.deviceId ?? "")
                        .font(.system(size: 10))
                        .foregroundStyle(.tertiary)
                }

                Spacer()

                Text("Paired")
                    .font(.system(size: 10))
                    .foregroundStyle(.green)
            }
            .padding()
            .background(Color(nsColor: .controlBackgroundColor))
            .cornerRadius(8)
        }
        .sheet(isPresented: $showPairingSheet) {
            DevicePairingWizard(isPresented: $showPairingSheet)
        }
    }
}

// MARK: - About Card

struct AboutCard: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("About Jarvis")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(.secondary)

            HStack(spacing: 16) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Version")
                        .font(.system(size: 10))
                        .foregroundStyle(.tertiary)

                    Text("0.1.0")
                        .font(.system(size: 12))
                }

                VStack(alignment: .leading, spacing: 4) {
                    Text("Build")
                        .font(.system(size: 10))
                        .foregroundStyle(.tertiary)

                    Text("2024.02.06")
                        .font(.system(size: 12))
                }

                Spacer()

                Button("Check for Updates") {
                    // TODO: Implement update check
                }
                .buttonStyle(.secondaryButtonStyle)
            }
            .padding()
            .background(Color(nsColor: .controlBackgroundColor))
            .cornerRadius(8)
        }
    }
}

// MARK: - Secondary Button Style

struct SecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 11, weight: .medium))
            .foregroundStyle(.secondary)
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .background(Color(nsColor: .controlBackgroundColor))
            .cornerRadius(4)
    }
}

extension ButtonStyle where Self == SecondaryButtonStyle {
    static var secondaryButtonStyle: SecondaryButtonStyle {
        SecondaryButtonStyle()
    }
}

// MARK: - Device Pairing Wizard

struct DevicePairingWizard: View {
    @Binding var isPresented: Bool
    @Environment(AuthManager.self) private var auth

    @State private var step = 1
    @State private var deviceName = ""
    @State private var pairingToken: String?
    @State private var isLoading = false

    var body: some View {
        VStack(spacing: 24) {
            // Header
            VStack(spacing: 4) {
                Text("Add New Device")
                    .font(.system(size: 16, weight: .semibold))

                Text(step == 1 ? "Enter device name" : "Scan QR code on new device")
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)
            }

            Divider()

            // Content
            Group {
                if step == 1 {
                    StepOne(deviceName: $deviceName, onNext: {
                        step = 2
                        initiatePairing()
                    })
                } else {
                    StepTwo(token: pairingToken ?? "", onConfirm: {
                        isPresented = false
                    })
                }
            }

            Spacer()
        }
        .padding(24)
        .frame(width: 400, height: 300)
    }

    private func initiatePairing() {
        isLoading = true
        Task {
            do {
                let response = try await auth.initiatePairing(deviceName: deviceName)
                pairingToken = response.token
            } catch {
                // Handle error
            }
            isLoading = false
        }
    }
}

struct StepOne: View {
    @Binding var deviceName: String
    let onNext: () -> Void

    var body: some View {
        VStack(spacing: 16) {
            TextField("Device Name", text: $deviceName)
                .textFieldStyle(.roundedBorder)
                .font(.system(size: 13))

            Button("Continue") {
                onNext()
            }
            .buttonStyle(.primaryButtonStyle)
            .disabled(deviceName.isEmpty)
        }
    }
}

struct StepTwo: View {
    let token: String
    let onConfirm: () -> Void

    var body: some View {
        VStack(spacing: 16) {
            QRCodeView(token: token)
                .frame(width: 150, height: 150)

            Text("Scan this code with the new device")
                .font(.system(size: 11))
                .foregroundStyle(.secondary)

            Button("Done") {
                onConfirm()
            }
            .buttonStyle(.primaryButtonStyle)
        }
    }
}

struct PrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 12, weight: .medium))
            .foregroundStyle(.white)
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(Color.accentColor)
            .cornerRadius(6)
    }
}

extension ButtonStyle where Self == PrimaryButtonStyle {
    static var primaryButtonStyle: PrimaryButtonStyle {
        PrimaryButtonStyle()
    }
}

// MARK: - QR Code View

struct QRCodeView: View {
    let token: String
    var isPresented: Binding<Bool>? = nil

    init(token: String, isPresented: Binding<Bool>? = nil) {
        self.token = token
        self.isPresented = isPresented
    }

    var body: some View {
        // Simplified QR placeholder
        ZStack {
            RoundedRectangle(cornerRadius: 12)
                .fill(Color.black)
                .frame(width: 150, height: 150)

            VStack(spacing: 8) {
                Image(systemName: "qrcode")
                    .font(.system(size: 60))
                    .foregroundStyle(.white)

                Text(token.prefix(8))
                    .font(.system(size: 10, family: .monospaced))
                    .foregroundStyle(.white.opacity(0.7))
            }
        }
        .onTapGesture {
            if let isPresented {
                isPresented.wrappedValue = false
            }
        }
    }
}

// MARK: - Device List View

struct DeviceListView: View {
    @Binding var isPresented: Bool
    @State private var devices: [DeviceInfo] = []

    var body: some View {
        VStack(spacing: 16) {
            Text("Registered Devices")
                .font(.system(size: 14, weight: .semibold))

            List {
                ForEach(devices) { device in
                    HStack {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundStyle(device.isActive ? .green : .red)

                        VStack(alignment: .leading) {
                            Text(device.name)
                                .font(.system(size: 12))

                            Text(device.id)
                                .font(.system(size: 10))
                                .foregroundStyle(.secondary)
                        }

                        Spacer()

                        if device.isActive {
                            Text("Active")
                                .font(.system(size: 10))
                                .foregroundStyle(.green)
                        }
                    }
                }
            }
            .listStyle(.bordered)
        }
        .padding(24)
        .frame(width: 400, height: 400)
    }
}
