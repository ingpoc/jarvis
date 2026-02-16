import Foundation
import UserNotifications
import OSLog

@Observable
class NotificationManager {
    static let shared = NotificationManager()
    private let logger = Logger(subsystem: "com.jarvis.app", category: "Notifications")

    private init() {}

    func requestAuthorization() async -> Bool {
        // Check if running in proper app bundle (not command-line)
        let bundlePath = Bundle.main.bundleURL.path
        let hasInfoPlist = FileManager.default.fileExists(atPath: bundlePath + "/Info.plist")

        guard hasInfoPlist else {
            // Silently skip - logging might also crash without bundle
            return false
        }

        let center = UNUserNotificationCenter.current()
        do {
            let granted = try await center.requestAuthorization(options: [.alert, .sound, .badge])
            if granted {
                logger.info("Notification authorization granted")
            } else {
                logger.error("Notification authorization denied")
            }
            return granted
        } catch {
            logger.error("Failed to request notification authorization: \(error.localizedDescription)")
            return false
        }
    }

    func notify(title: String, body: String, sound: UNNotificationSound = .default) {
        // Only send notifications if running in proper app bundle
        guard Bundle.main.bundleURL.pathExtension == "app" else {
            return
        }

        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = sound

        let request = UNNotificationRequest(
            identifier: UUID().uuidString,
            content: content,
            trigger: nil
        )

        UNUserNotificationCenter.current().add(request) { error in
            if let error = error {
                self.logger.error("Failed to send notification: \(error.localizedDescription)")
            } else {
                self.logger.info("Notification sent: \(title)")
            }
        }
    }

    func notifyApprovalNeeded(summary: String, taskId: String) {
        notify(
            title: "Jarvis Approval Needed",
            body: summary
        )
    }

    func notifyError(_ message: String) {
        notify(
            title: "Jarvis Error",
            body: message,
            sound: .defaultCritical
        )
    }

    func notifyTaskComplete(summary: String) {
        notify(
            title: "Jarvis Task Complete",
            body: summary,
            sound: .default
        )
    }
}
