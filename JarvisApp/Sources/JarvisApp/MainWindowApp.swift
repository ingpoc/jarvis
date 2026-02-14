import SwiftUI
import Observation

@main
struct JarvisApp: App {
    @State private var router = NavigationRouter()
    @State private var authManager = AuthManager.shared

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(authManager)
                .environment(router)
                .frame(minWidth: 800, minHeight: 600)
        }
        .windowStyle(.hiddenTitleBar)
        .defaultSize(width: 1000, height: 700)

        MenuBarExtra {
            JarvisMenuView()
                .environment(authManager)
                .frame(width: 360, height: 480)
        } label: {
            MenuBarIcon(status: router.currentStatus)
        }
        .menuBarExtraStyle(.window)
    }
}

// MARK: - Navigation Router

@Observable
@available(macOS 14, *)
public final class NavigationRouter {
    public enum Tab: String, CaseIterable {
        case dashboard = "Dashboard"
        case timeline = "Timeline"
        case commands = "Commands"
        case voice = "Voice"
        case settings = "Settings"
    }

    public private(set) var selectedTab: Tab = .dashboard
    public private(set) var currentStatus: JarvisStatus = .idle

    public func selectTab(_ tab: Tab) {
        selectedTab = tab
    }

    public func updateStatus(_ status: JarvisStatus) {
        currentStatus = status
    }
}

// MARK: - Menu Bar Icon

struct MenuBarIcon: View {
    let status: JarvisStatus

    var body: some View {
        Image(systemName: "brain.head.profile")
            .symbolRenderingMode(.palette)
            .foregroundStyle(status.color)
            .font(.system(size: 14, weight: .medium))
    }
}

// MARK: - Main Content View

struct ContentView: View {
    @Environment(AuthManager.self) private var auth
    @Environment(NavigationRouter.self) private var router
    @State private var showSetupWizard = false

    var body: some View {
        Group {
            if auth.isAuthenticated {
                MainView()
            } else {
                SetupWizardView()
            }
        }
        .onAppear {
            showSetupWizard = !auth.isAuthenticated
        }
        .sheet(isPresented: $showSetupWizard) {
            if !auth.isAuthenticated {
                SetupWizardView(isPresented: $showSetupWizard)
                    .frame(width: 500, height: 400)
            }
        }
    }
}

// MARK: - Main View

struct MainView: View {
    @Environment(NavigationRouter.self) private var router

    var body: some View {
        NavigationSplitView {
            SidebarView()
        } detail: {
            DetailView()
        }
        .navigationSplitViewStyle(.balanced)
    }
}

// MARK: - Sidebar

struct SidebarView: View {
    @Environment(NavigationRouter.self) private var router
    @Environment(AuthManager.self) private var auth

    var body: some View {
        VStack(spacing: 0) {
            // Status Header
            HStack {
                StatusIndicator(status: router.currentStatus)
                    .frame(width: 8, height: 8)

                Text(router.currentStatus.label)
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(.secondary)

                Spacer()

                Text(auth.currentToken?.deviceName ?? "Unknown")
                    .font(.system(size: 10))
                    .foregroundStyle(.tertiary)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(Color(nsColor: .controlBackgroundColor))

            Divider()

            // Navigation Items
            ForEach(NavigationRouter.Tab.allCases, id: \.self) { tab in
                NavigationItem(
                    tab: tab,
                    isSelected: router.selectedTab == tab
                ) {
                    router.selectTab(tab)
                }
            }

            Spacer()
        }
        .frame(maxWidth: 180)
        .background(Color(nsColor: .sidebarBackgroundColor))
    }
}

// MARK: - Navigation Item

struct NavigationItem: View {
    let tab: NavigationRouter.Tab
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                Image(systemName: iconName)
                    .frame(width: 16)

                Text(tab.rawValue)
                    .font(.system(size: 12, weight: isSelected ? .semibold : .regular))

                Spacer()
            }
            .foregroundStyle(isSelected ? .primary : .secondary)
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(isSelected ? Color.accentColor.opacity(0.1) : Color.clear)
            .cornerRadius(4)
        }
        .buttonStyle(.plain)
        .padding(.horizontal, 8)
        .padding(.vertical, 2)
    }

    private var iconName: String {
        switch tab {
        case .dashboard: return "chart.bar.fill"
        case .timeline: return "clock.fill"
        case .commands: return "terminal.fill"
        case .voice: return "waveform"
        case .settings: return "gearshape.fill"
        }
    }
}

// MARK: - Detail View

struct DetailView: View {
    @Environment(NavigationRouter.self) private var router

    var body: some View {
        Group {
            switch router.selectedTab {
            case .dashboard:
                DashboardView()
            case .timeline:
                TimelineView()
            case .commands:
                CommandView()
            case .voice:
                VoiceView()
            case .settings:
                SettingsView()
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(nsColor: .textBackgroundColor))
    }
}

// MARK: - Status Indicator

struct StatusIndicator: View {
    let status: JarvisStatus

    var body: some View {
        Circle()
            .fill(status.color)
            .glow(radius: 4)
    }
}

extension View {
    func glow(radius: CGFloat) -> some View {
        self
            .shadow(color: .primary.opacity(0.3), radius: radius)
    }
}
