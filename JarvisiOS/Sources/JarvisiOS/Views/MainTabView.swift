import SwiftUI
import JarvisClient

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
