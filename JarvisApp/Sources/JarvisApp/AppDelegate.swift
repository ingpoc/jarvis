import Cocoa
import CoreSpotlight
import OSLog
import UniformTypeIdentifiers

// MARK: - App Delegate

class AppDelegate: NSObject, NSApplicationDelegate {
    private let logger = Logger(subsystem: "com.jarvis.app", category: "AppDelegate")

    func application(
        _ application: NSApplication,
        continue userActivity: NSUserActivity,
        restorationHandler: @escaping ([NSUserActivityRestoring]) -> Void
    ) -> Bool {
        guard userActivity.activityType == CSSearchableItemActionType else {
            return false
        }

        logger.info("Received Spotlight activity: \(userActivity.activityType)")

        // Activate app to bring it to front
        NSApp.activate(ignoringOtherApps: true)

        // TODO: Navigate to appropriate view based on identifier
        // let identifier = userActivity.userInfo?[CSSearchableItemActivityIdentifier] as? String ?? ""

        return true
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        logger.info("Jarvis app finished launching")

        // Register global hotkeys after app has launched
        Task { @MainActor in
            MenuBarManager.shared.registerGlobalHotkeys()
        }
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        // Clean up on exit
        Task { @MainActor in
            // Unregister global hotkeys
            MenuBarManager.shared.unregisterGlobalHotkeys()

            // Optional: uncomment to clear all Spotlight items on exit
            // SpotlightService.shared.clearAllItems()
        }
        return .terminateNow
    }
}
