import SwiftUI
import JarvisClient

struct SettingsTab: View {
    @Environment(AuthManager.self) private var auth

    var body: some View {
        NavigationStack {
            List {
                Section {
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(auth.currentToken?.deviceName ?? "Unknown Device")
                                .font(.system(size: 16))

                            Text(auth.currentToken?.deviceId ?? "")
                                .font(.system(size: 12))
                                .foregroundStyle(.secondary)
                        }

                        Spacer()

                        Image(systemName: "checkmark.circle.fill")
                            .foregroundStyle(.green)
                    }
                } header: {
                    Text("Device")
                }

                Section {
                    HStack {
                        Text("Server")
                        Spacer()
                        Text(auth.serverURL.host ?? "Unknown")
                            .foregroundStyle(.secondary)
                    }

                    HStack {
                        Text("Status")
                        Spacer()
                        Text("Connected")
                            .foregroundStyle(.green)
                    }
                } header: {
                    Text("Connection")
                }

                Section {
                    HStack {
                        Text("Face ID")
                        Spacer()
                        Toggle("", isOn: .constant(true))
                    }

                    HStack {
                        Text("Notifications")
                        Spacer()
                        Toggle("", isOn: .constant(true))
                    }

                    HStack {
                        Text("Haptic Feedback")
                        Spacer()
                        Toggle("", isOn: .constant(true))
                    }
                } header: {
                    Text("Settings")
                }

                Section {
                    HStack {
                        Text("Version")
                        Spacer()
                        Text("0.1.0")
                            .foregroundStyle(.secondary)
                    }

                    Button("Terms of Service") {}
                    Button("Privacy Policy") {}
                } header: {
                    Text("About")
                }
            }
            .navigationTitle("Settings")
        }
    }
}
