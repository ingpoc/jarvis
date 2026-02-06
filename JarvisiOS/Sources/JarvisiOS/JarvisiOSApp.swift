import SwiftUI
import JarvisClient

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
    }
}
