import SwiftUI

@main
struct JarvisiOSApp: App {
    @State private var authManager = AuthManager.shared
    @State private var hasCompletedOnboarding = UserDefaults.standard.bool(forKey: "hasCompletedOnboarding")

    var body: some Scene {
        WindowGroup {
            Group {
                if hasCompletedOnboarding {
                    MainTabView()
                } else {
                    OnboardingView(isPresented: .constant(true)) {
                        hasCompletedOnboarding = true
                        UserDefaults.standard.set(true, forKey: "hasCompletedOnboarding")
                    }
                }
            }
            .environment(authManager)
        }
        .modelContainer(for: [TimelineEvent.self])
    }
}

// MARK: - Main Tab View

struct MainTabView: View {
    @Environment(AuthManager.self) private var auth

    var body: some View {
        TabView {
            DashboardTab()
                .tabItem {
                    Label("Dashboard", systemImage: "chart.bar.fill")
                }

            TimelineTab()
                .tabItem {
                    Label("Timeline", systemImage: "clock.fill")
                }

            VoiceTab()
                .tabItem {
                    Label("Voice", systemImage: "waveform")
                }

            SettingsTab()
                .tabItem {
                    Label("Settings", systemImage: "gearshape.fill")
                }
        }
        .tint(.accentColor)
    }
}

// MARK: - Onboarding View

struct OnboardingView: View {
    @Binding var isPresented: Bool
    let onComplete: () -> Void

    @State private var currentPage = 0

    var body: some View {
        TabView(selection: $currentPage) {
            OnboardingPage(
                icon: "brain.head.profile",
                title: "Meet Jarvis",
                description: "Your autonomous development partner, now in your pocket.",
                action: {
                    Button("Continue") { currentPage = 1 }
                }
            )

            OnboardingPage(
                icon: "waveform",
                title: "Voice Control",
                description: "Give commands naturally. Jarvis understands context.",
                action: {
                    Button("Continue") { currentPage = 2 }
                }
            )

            OnboardingPage(
                icon: "gearshape.fill",
                title: "Get Started",
                description: "Pair with your Jarvis server to begin.",
                action: {
                    Button("Pair Now") {
                        onComplete()
                    }
                    .buttonStyle(.primaryButtonStyle())
                }
            )
        }
        .indexViewStyle(.page(backgroundDisplayMode: .always))
        .ignoresSafeArea(.keyboard)
    }
}

struct OnboardingPage: View {
    let icon: String
    let title: String
    let description: String
    let action: () -> Void

    var body: some View {
        VStack(spacing: 32) {
            Spacer()

            Image(systemName: icon)
                .font(.system(size: 72))
                .foregroundStyle(.accentColor)

            VStack(spacing: 12) {
                Text(title)
                    .font(.system(size: 28, weight: .bold))

                Text(description)
                    .font(.system(size: 16))
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            }

            Spacer()

            action()
        }
        .padding()
    }
}

// MARK: - Dashboard Tab

struct DashboardTab: View {
    @State private var client = WebSocketClient(
        serverURL: URL(string: "wss://localhost:9848")!
    )

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    // Status Card
                    StatusCard(status: client.status)
                        .padding(.horizontal)

                    // Quick Actions
                    QuickActionsGrid()
                        .padding(.horizontal)

                    // Recent Activity
                    RecentActivityPreview(events: client.events)
                        .padding(.horizontal)
                }
                .padding(.vertical)
            }
            .background(Color(UIColor.systemGroupedBackground))
        }
        .onAppear { client.connect() }
        .onDisappear { client.disconnect() }
    }
}

struct StatusCard: View {
    let status: JarvisStatus

    var body: some View {
        HStack(spacing: 16) {
            ZStack {
                Circle()
                    .fill(status.color.opacity(0.15))
                    .frame(width: 60, height: 60)

                Circle()
                    .fill(status.color)
                    .frame(width: 16, height: 16)
            }

            VStack(alignment: .leading, spacing: 4) {
                Text(status.label)
                    .font(.system(size: 20, weight: .semibold))

                Text(statusMessage)
                    .font(.system(size: 14))
                    .foregroundStyle(.secondary)
            }

            Spacer()
        }
        .padding()
        .background(Color(UIColor.secondarySystemGroupedBackground))
        .cornerRadius(12)
    }

    private var statusMessage: String {
        switch status {
        case .idle: return "Ready for commands"
        case .building: return "Building project..."
        case .testing: return "Running tests..."
        case .error: return "Error occurred"
        case .waitingApproval: return "Awaiting approval"
        }
    }
}

struct QuickActionsGrid: View {
    let actions = [
        (icon: "testtube.2", title: "Test", color: Color.blue),
        (icon: "hammer", title: "Build", color: Color.orange),
        (icon: "sparkles", title: "Clean", color: Color.purple),
        (icon: "branch", title: "Git", color: Color.green),
    ]

    var body: some View {
        LazyVGrid(columns: [
            GridItem(.flexible(), spacing: 12),
            GridItem(.flexible(), spacing: 12),
        ], spacing: 12) {
            ForEach(actions, id: \.title) { action in
                QuickActionButton(
                    icon: action.icon,
                    title: action.title,
                    color: action.color
                )
            }
        }
    }
}

struct QuickActionButton: View {
    let icon: String
    let title: String
    let color: Color

    var body: some View {
        Button(action: {
            // Haptic feedback
            let generator = UIImpactFeedbackGenerator(style: .light)
            generator.impactOccurred()
        }) {
            VStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.system(size: 24))

                Text(title)
                    .font(.system(size: 12, weight: .medium))
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 20)
            .background(Color(UIColor.secondarySystemGroupedBackground))
            .foregroundStyle(color)
            .cornerRadius(10)
        }
        .buttonStyle(.plain)
    }
}

struct RecentActivityPreview: View {
    let events: [TimelineEvent]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Recent Activity")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(.secondary)
                .padding(.horizontal, 4)

            VStack(spacing: 0) {
                ForEach(Array(events.prefix(3).enumerated()), id: \.element.id) { index, event in
                    EventRow(event: event)
                    if index < min(events.count, 3) - 1 {
                        Divider().padding(.leading, 44)
                    }
                }
            }
            .background(Color(UIColor.secondarySystemGroupedBackground))
            .cornerRadius(10)
        }
    }
}

struct EventRow: View {
    let event: TimelineEvent

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: iconName)
                .font(.system(size: 12))
                .foregroundStyle(iconColor)
                .frame(width: 20)

            Text(event.summary)
                .font(.system(size: 13))
                .lineLimit(1)

            Spacer()

            Text(event.timeString)
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
    }

    private var iconName: String {
        switch event.eventType {
        case "error": return "xmark.circle"
        case "approval_needed": return "hand.raised"
        case "task_complete": return "checkmark.circle"
        default: return "circle"
        }
    }

    private var iconColor: Color {
        switch event.eventType {
        case "error": return .red
        case "approval_needed": return .orange
        case "task_complete": return .green
        default: return .secondary
        }
    }
}

// MARK: - Timeline Tab

struct TimelineTab: View {
    @State private var client = WebSocketClient(
        serverURL: URL(string: "wss://localhost:9848")!
    )

    var body: some View {
        NavigationStack {
            List {
                ForEach(client.events) { event in
                    EventDetailRow(event: event)
                        .contentShape(Rectangle())
                        .onTapGesture {
                            // Show detail
                        }
                }
            }
            .listStyle(.insetGrouped)
            .refreshable {
                await refreshTimeline()
            }
            .navigationTitle("Timeline")
        }
        .onAppear { client.connect() }
        .onDisappear { client.disconnect() }
    }

    private func refreshTimeline() async {
        // Pull to refresh logic
    }
}

struct EventDetailRow: View {
    let event: TimelineEvent

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: iconName)
                .font(.system(size: 14))
                .foregroundStyle(iconColor)
                .frame(width: 24)

            VStack(alignment: .leading, spacing: 4) {
                Text(event.summary)
                    .font(.system(size: 14))

                HStack(spacing: 8) {
                    Text(event.timeString)
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)

                    if let cost = event.costUsd, cost > 0 {
                        Text("•")
                            .foregroundStyle(.secondary)

                        Text("$\(String(format: "%.2f", cost))")
                            .font(.system(size: 11))
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
        .padding(.vertical, 4)
    }

    private var iconName: String {
        switch event.eventType {
        case "error": return "xmark.circle.fill"
        case "approval_needed": return "hand.raised.fill"
        case "task_start": return "play.circle.fill"
        case "task_complete": return "checkmark.circle.fill"
        case "feature_start": return "sparkles"
        case "tool_use": return "wrench.and.screwdriver"
        default: return "circle.fill"
        }
    }

    private var iconColor: Color {
        switch event.eventType {
        case "error": return .red
        case "approval_needed": return .orange
        case "task_start": return .blue
        case "task_complete": return .green
        case "feature_complete": return .green
        default: return .secondary
        }
    }
}

// MARK: - Voice Tab

struct VoiceTab: View {
    @State private var isRecording = false
    @State private var transcript = ""

    var body: some View {
        NavigationStack {
            VStack(spacing: 32) {
                VStack(spacing: 8) {
                    Text("Voice Command")
                        .font(.system(size: 20, weight: .semibold))

                    Text("Hold button to speak")
                        .font(.system(size: 14))
                        .foregroundStyle(.secondary)
                }

                Spacer()

                // Voice button
                VoiceRecordingButton(
                    isRecording: $isRecording,
                    transcript: $transcript
                )

                // Transcript
                if !transcript.isEmpty {
                    VStack(spacing: 8) {
                        Text("You said:")
                            .font(.system(size: 12))
                            .foregroundStyle(.secondary)

                        Text(transcript)
                            .font(.system(size: 16))
                            .multilineTextAlignment(.center)
                    }
                    .padding()
                    .background(Color(UIColor.secondarySystemGroupedBackground))
                    .cornerRadius(10)
                }

                Spacer()
            }
            .padding()
            .navigationTitle("Voice")
        }
    }
}

struct VoiceRecordingButton: View {
    @Binding var isRecording: Bool
    @Binding var transcript: String

    var body: some View {
        ZStack {
            if isRecording {
                Circle()
                    .fill(Color.red.opacity(0.2))
                    .frame(width: 160, height: 160)
                    .scaleEffect(isRecording ? 1.2 : 1.0)
                    .animation(.easeInOut(duration: 1.0).repeatForever(autoreverses: true), value: isRecording)
            }

            Button(action: toggleRecording) {
                ZStack {
                    Circle()
                        .fill(isRecording ? Color.red : Color.accentColor)
                        .frame(width: 100, height: 100)

                    Image(systemName: isRecording ? "stop.fill" : "mic.fill")
                        .font(.system(size: 32))
                        .foregroundStyle(.white)
                }
            }
            .buttonStyle(.plain)
        }
        .onLongPressGesture(minimumDuration: 0, pressing: { pressing in
            if pressing && !isRecording {
                isRecording = true
                startRecording()
            } else if !pressing && isRecording {
                isRecording = false
                stopRecording()
            }
        }, perform: {})
    }

    private func toggleRecording() {
        isRecording.toggle()
    }

    private func startRecording() {
        // Haptic feedback
        let generator = UIImpactFeedbackGenerator(style: .medium)
        generator.impactOccurred()
    }

    private func stopRecording() {
        // Haptic feedback
        let generator = UIImpactFeedbackGenerator(style: .light)
        generator.impactOccurred()

        // Simulate transcript
        transcript = "Run the test suite"
    }
}

// MARK: - Settings Tab

struct SettingsTab: View {
    @Environment(AuthManager.self) private var auth

    var body: some View {
        NavigationStack {
            List {
                // Account Section
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

                // Connection Section
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

                // App Settings
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

                // About
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

// MARK: - Button Styles

struct PrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 16, weight: .semibold))
            .foregroundStyle(.white)
            .padding(.horizontal, 32)
            .padding(.vertical, 14)
            .frame(maxWidth: .infinity)
            .background(Color.accentColor)
            .cornerRadius(12)
    }
}

// Swift 5.10 / iOS 17+ compatibility
@available(iOS 17, *)
extension ButtonStyle where Self == PrimaryButtonStyle {
    static func primaryButtonStyle() -> PrimaryButtonStyle {
        PrimaryButtonStyle()
    }
}
