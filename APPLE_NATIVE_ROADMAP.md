# Jarvis Apple Native Integration Roadmap

## Executive Summary

This roadmap prioritizes Apple native framework integrations for Jarvis, a macOS-based autonomous development assistant. The current implementation uses a Python daemon with a SwiftUI menu bar app communicating via WebSocket.

**Current State:**

- ~750 lines of Swift code (menu bar app)
- Python daemon with WebSocket bridge
- Basic container monitoring and timeline visualization
- Voice integration via ElevenLabs
- Slack bot integration

**Target State:**

- Fully native macOS experience using Apple frameworks
- SwiftUI app with proper MVVM architecture
- Native notifications, accessibility, and system integration
- Optional iOS companion app

---

## Tier 1: Quick Wins (Under 4 hours each)

### T1.1 Fix Critical Swift Issues (Priority: 10/10, Effort: 2h)

**Impact:** Prevents crashes, improves reliability

**Files to Modify:**

- `JarvisApp/Sources/JarvisApp/WebSocketClient.swift`
- `JarvisApp/Sources/JarvisApp/Models/*.swift`

**Implementation Steps:**

1. Fix force-unwrapped URL (WebSocketClient.swift:15)

```swift
// BEFORE (crashes if invalid)
private let url = URL(string: "ws://127.0.0.1:9847")!

// AFTER
private let url: URL
init() {
    guard let url = URL(string: "ws://127.0.0.1:9847") else {
        fatalError("Invalid WebSocket URL configuration")
    }
    self.url = url
}
```

1. Fix main thread violations (WebSocketClient.swift:21-22)

```swift
// Add DispatchQueue.main.async wrapper
DispatchQueue.main.async {
    self.isConnected = true
}
```

1. Fix silent JSON decode failures (WebSocketClient.swift:95-96)

```swift
do {
    let event = try JSONDecoder().decode(TimelineEvent.self, from: eventData)
    events.insert(event, at: 0)
} catch {
    logger.error("Failed to decode TimelineEvent: \(error)")
    lastError = "Invalid event data from server"
}
```

1. Fix TimelineEvent.id optional violation of Identifiable

```swift
// TimelineEvent.swift
struct TimelineEvent: Identifiable, Codable {
    let id: String  // Change from Int? to String
    // Use timestamp + eventType for uniqueness
}
```

**Dependencies:** None

**Success Metrics:**

- No force-unwrap warnings in build
- All JSON errors logged
- No main thread violations

---

### T1.2 Separate View Logic from Models (Priority: 9/10, Effort: 1.5h)

**Impact:** Proper MVVM, testable models

**Files to Modify:**

- `JarvisApp/Sources/JarvisApp/Models/ContainerInfo.swift`
- `JarvisApp/Sources/JarvisApp/Models/JarvisStatus.swift`
- Create: `JarvisApp/Sources/JarvisApp/Utils/ViewExtensions.swift`

**Implementation Steps:**

1. Remove SwiftUI imports from models

```swift
// ContainerInfo.swift - remove import SwiftUI
// Remove statusColor computed property
```

1. Create view extensions in separate file

```swift
// ViewExtensions.swift
import SwiftUI

extension ContainerInfo {
    var statusColor: Color {
        switch status.lowercased() {
        case "running": .green
        case "stopped", "exited": .red
        case "paused": .yellow
        default: .secondary
        }
    }
}

extension JarvisStatus {
    var color: Color { /* existing code */ }
}
```

**Dependencies:** T1.1

**Success Metrics:**

- Models compile without SwiftUI
- Unit tests can import models alone
- Views use extensions for presentation

---

### T1.3 Add Accessibility Support (Priority: 8/10, Effort: 2h)

**Impact:** VoiceOver compatibility, inclusive design

**Files to Modify:**

- `JarvisApp/Sources/JarvisApp/Views/CommandCenterView.swift`
- `JarvisApp/Sources/JarvisApp/Views/TimelineView.swift`
- `JarvisApp/Sources/JarvisApp/Views/StatusBadge.swift`

**Implementation Steps:**

1. Replace color-only status indicators with icons

```swift
// CommandCenterView.swift:74-76
// BEFORE (color only)
Circle()
    .fill(container.statusColor)
    .frame(width: 8, height: 8)

// AFTER (icon + color)
Image(systemName: container.statusIcon)
    .foregroundStyle(container.statusColor)

// Add to ContainerInfo extension
var statusIcon: String {
    switch status.lowercased() {
    case "running": return "checkmark.circle.fill"
    case "stopped": return "xmark.circle.fill"
    case "paused": return "pause.circle.fill"
    default: return "questionmark.circle.fill"
    }
}
```

1. Add accessibility labels

```swift
Circle()
    .fill(ws.status.color)
    .accessibilityLabel("Status: \(ws.status.label)")
    .accessibilityValue(ws.isConnected ? "Connected" : "Disconnected")
```

**Dependencies:** None

**Success Metrics:**

- VoiceOver announces all status changes
- No color-only indicators remain
- Accessibility audit passes

---

### T1.4 Create Shared EventColors Utility (Priority: 7/10, Effort: 0.5h)

**Impact:** Consistent UI, eliminates duplicate code

**Files to Modify:**

- Create: `JarvisApp/Sources/JarvisApp/Utils/EventColors.swift`
- `JarvisApp/Sources/JarvisApp/Views/TimelineView.swift`
- `JarvisApp/Sources/JarvisApp/Views/CommandCenterView.swift`

**Implementation Steps:**

1. Create centralized color utility

```swift
// EventColors.swift
import SwiftUI

struct EventColors {
    static func color(for eventType: String) -> Color {
        switch eventType {
        case "tool_use": .blue
        case "approval_needed": .orange
        case "error", "failure": .red
        case "success", "complete": .green
        case "build_start", "build_end": .blue
        case "test_start", "test_end": .yellow
        default: .primary
        }
    }
}
```

1. Replace duplicate colorForType functions

**Dependencies:** None

**Success Metrics:**

- Single source of truth for event colors
- Color changes propagate everywhere

---

### T1.5 Add Loading and Error States (Priority: 7/10, Effort: 1.5h)

**Impact:** Better UX, clear feedback

**Files to Modify:**

- `JarvisApp/Sources/JarvisApp/WebSocketClient.swift`
- `JarvisApp/Sources/JarvisApp/Views/CommandCenterView.swift`
- `JarvisApp/Sources/JarvisApp/Views/JarvisMenuView.swift`

**Implementation Steps:**

1. Add loading/error states to WebSocketClient

```swift
@Observable final class WebSocketClient {
    var isLoading = false
    var lastError: String?

    func refreshContainers() async {
        isLoading = true
        defer { isLoading = false }
        sendCommand(action: "get_containers")
    }
}
```

1. Update UI to show states

```swift
Button("Refresh") {
    Task { await ws.refreshContainers() }
}
.disabled(ws.isLoading)
```

**Dependencies:** T1.1

**Success Metrics:**

- All async operations show loading state
- Errors displayed to users
- No silent failures

---

### T1.6 Add Native macOS Notifications (Priority: 8/10, Effort: 2h)

**Impact:** Better system integration, native alerts

**Files to Modify:**

- Create: `JarvisApp/Sources/JarvisApp/Utils/NotificationManager.swift`
- `JarvisApp/Sources/JarvisApp/WebSocketClient.swift`

**Implementation Steps:**

1. Create notification manager

```swift
// NotificationManager.swift
import UserNotifications

@Observable
class NotificationManager {
    static let shared = NotificationManager()

    func requestAuthorization() async -> Bool {
        let center = UNUserNotificationCenter.current()
        try? await center.requestAuthorization(options: [.alert, .sound, .badge])
        return true
    }

    func notify(title: String, body: String, sound: UNNotificationSound = .default) {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = sound

        let request = UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil)
        UNUserNotificationCenter.current().add(request)
    }
}
```

1. Send notifications for approval events

```swift
private func handleEvent(_ data: [String: Any]) {
    // existing code...
    if event.eventType == "approval_needed" {
        Task {
            await NotificationManager.shared.notify(
                title: "Jarvis Approval Needed",
                body: event.summary
            )
        }
    }
}
```

1. Request authorization on app launch

**Dependencies:** None

**Success Metrics:**

- Notifications appear for approvals/errors
- System notification settings work
- Sounds play correctly

---

### T1.7 Create Design System Constants (Priority: 6/10, Effort: 1h)

**Impact:** Consistent spacing, colors, easier maintenance

**Files to Modify:**

- Create: `JarvisApp/Sources/JarvisApp/Utils/DesignSystem.swift`

**Implementation Steps:**

1. Define design tokens

```swift
// DesignSystem.swift
import SwiftUI

struct DesignSystem {
    struct Spacing {
        static let xs: CGFloat = 4
        static let sm: CGFloat = 8
        static let md: CGFloat = 12
        static let lg: CGFloat = 16
        static let xl: CGFloat = 24
    }

    struct Colors {
        static let statusRunning = Color.green
        static let statusStopped = Color.red
        static let statusPaused = Color.yellow
        static let statusError = Color.red
    }

    struct Typography {
        static let largeTitle = Font.largeTitle
        static let title = Font.title
        static let headline = Font.headline
        static let body = Font.body
        static let caption = Font.caption
    }
}
```

1. Replace hardcoded values throughout views

**Dependencies:** None

**Success Metrics:**

- No hardcoded spacing values
- Consistent visual appearance
- Easy to adjust design

---

## Tier 2: Medium-Term (1-2 weeks)

### T2.1 Implement Proper WebSocket Protocol (Priority: 9/10, Effort: 8h)

**Impact:** Reliable communication, error recovery

**Files to Modify:**

- `JarvisApp/Sources/JarvisApp/WebSocketClient.swift`
- Create: `JarvisApp/Sources/JarvisApp/Models/WebSocketProtocol.swift`

**Implementation Steps:**

1. Define protocol for testability

```swift
// WebSocketProtocol.swift
protocol WebSocketProtocol: AnyObject {
    var isConnected: Bool { get }
    func connect()
    func disconnect()
    func send(_ text: String) async throws
    var onMessage: ((String) -> Void)? { get set }
    var onError: ((Error) -> Void)? { get set }
}
```

1. Add reconnection with exponential backoff

```swift
private var reconnectAttempts = 0
private let maxReconnectAttempts = 5

private func scheduleReconnect() {
    reconnectWork?.cancel()
    guard reconnectAttempts < maxReconnectAttempts else { return }

    let delay = pow(2.0, Double(reconnectAttempts))  // 1s, 2s, 4s, 8s, 16s
    reconnectAttempts += 1

    let work = DispatchWorkItem { [weak self] in
        self?.connect()
    }
    reconnectWork = work
    DispatchQueue.main.asyncAfter(deadline: .now() + delay, execute: work)
}
```

1. Add request/response correlation

```swift
struct PendingRequest {
    let id: String
    let action: String
    let callback: (Result<Any, Error>) -> Void
}

private var pendingRequests: [String: PendingRequest] = [:]

func sendCommand<T: Decodable>(action: String, data: [String: Any] = []) async throws -> T {
    let requestId = UUID().uuidString
    // Add request_id to payload
    // Await callback
}
```

1. Add proper error handling to send

```swift
task?.send(.string(text)) { [weak self] error in
    if let error = error {
        DispatchQueue.main.async {
            self?.isConnected = false
            self?.lastError = error.localizedDescription
        }
    }
}
```

**Dependencies:** T1.1, T1.5

**Success Metrics:**

- Automatic reconnection works
- All messages correlated
- Mockable for testing

---

### T2.2 Implement MVVM Architecture (Priority: 8/10, Effort: 12h)

**Impact:** Testable, maintainable code

**Files to Modify:**

- Create: `JarvisApp/Sources/JarvisApp/ViewModels/*.swift`
- Refactor: All views to use ViewModels

**Implementation Steps:**

1. Create base ViewModel

```swift
// BaseViewModel.swift
import SwiftUI

@Observable
class BaseViewModel {
    var isLoading = false
    var errorMessage: String?

    func clearError() {
        errorMessage = nil
    }
}
```

1. Create ViewModels for each screen

```swift
// CommandCenterViewModel.swift
@Observable
class CommandCenterViewModel: BaseViewModel {
    private(set) var containers: [ContainerInfo] = []

    func loadContainers() async {
        isLoading = true
        defer { isLoading = false }

        // Fetch logic
    }
}
```

1. Update views to use ViewModels

```swift
struct CommandCenterView: View {
    @State private var viewModel = CommandCenterViewModel()

    var body: some View {
        // Use viewModel properties
    }
}
```

**Dependencies:** T2.1

**Success Metrics:**

- Views contain only UI code
- ViewModels testable without SwiftUI
- Clear separation of concerns

---

### T2.3 Add Local Persistence (Priority: 7/10, Effort: 8h)

**Impact:** Offline capability, faster startup

**Files to Modify:**

- Create: `JarvisApp/Sources/JarvisApp/Services/PersistenceService.swift`
- Update: ViewModels to use persistence

**Implementation Steps:**

1. Create persistence using UserDefaults + SwiftData

```swift
// PersistenceService.swift
import SwiftData

@Model
class StoredEvent {
    var id: String
    var timestamp: Double
    var eventType: String
    var summary: String
    var data: Data
}

actor PersistenceService {
    static let shared = PersistenceService()

    private let modelContainer: ModelContainer

    init() {
        let schema = Schema([StoredEvent.self])
        let configuration = ModelConfiguration(isStoredInMemoryOnly: false)
        modelContainer = try! ModelContainer(for: schema, configurations: [configuration])
    }

    func saveEvent(_ event: TimelineEvent) {
        // Save to SwiftData
    }

    func loadEvents() -> [TimelineEvent] {
        // Load from SwiftData
    }
}
```

1. Cache events locally
2. Show cached data while disconnected
3. Sync with server on reconnect

**Dependencies:** T2.2

**Success Metrics:**

- Timeline persists across restarts
- Shows cached data when offline
- Syncs on reconnect

---

### T2.4 Add macOS Menu Bar Native Features (Priority: 8/10, Effort: 6h)

**Impact:** Better system integration

**Files to Modify:**

- `JarvisApp/Sources/JarvisApp/JarvisApp.swift`
- Create: `JarvisApp/Sources/JarvisApp/Utils/MenuBarManager.swift`

**Implementation Steps:**

1. Add keyboard shortcut for quick actions

```swift
// Hotkey to open Jarvis
NSEvent.addLocalMonitorForEvents(matching: .keyDown) { event in
    if event.modifierFlags.contains([.command, .shift]) && event.keyCode == 9 {
        // Cmd+Shift+J - Toggle Jarvis
        NSApp.activate(ignoringOtherApps: true)
    }
    return event
}
```

1. Add drag-and-drop support for files

```swift
.onDrop(of: [.fileURL], isTargeted: nil) { providers in
    // Handle dropped files
    return true
}
```

1. Add quick actions menu

```swift
Menu("Quick Actions") {
    Button("Run Tests") { /* */ }
    Button("Build Project") { /* */ }
    Button("Git Status") { /* */ }
}
```

**Dependencies:** None

**Success Metrics:**

- Keyboard shortcuts work
- Drag-drop opens files
- Quick actions accessible

---

### T2.5 Implement Better Error Handling (Priority: 8/10, Effort: 6h)

**Impact:** Better UX, easier debugging

**Files to Modify:**

- Create: `JarvisApp/Sources/JarvisApp/Utils/ErrorHandler.swift`
- Update: All error-producing code

**Implementation Steps:**

1. Define app errors

```swift
// AppError.swift
enum AppError: LocalizedError {
    case websocketDisconnected
    case invalidResponse
    case serverError(String)

    var errorDescription: String? {
        switch self {
        case .websocketDisconnected: return "Connection to Jarvis lost"
        case .invalidResponse: return "Invalid response from server"
        case .serverError(let msg): return "Server error: \(msg)"
        }
    }
}
```

1. Create error handler

```swift
@Observable
class ErrorHandler {
    static let shared = ErrorHandler()
    var currentError: AppError?
    var showErrorAlert = false

    func handle(_ error: AppError) {
        currentError = error
        showErrorAlert = true
    }
}
```

1. Add error banner to UI

```swift
if let errorHandler = ErrorHandler.shared.currentError {
    HStack {
        Image(systemName: "exclamationmark.triangle.fill")
        Text(errorHandler.errorDescription)
        Button("Dismiss") { ErrorHandler.shared.clearError() }
    }
    .padding()
    .background(Color.red.opacity(0.1))
}
```

**Dependencies:** T2.1, T2.2

**Success Metrics:**

- All errors caught and displayed
- User-friendly error messages
- Errors logged for debugging

---

### T2.6 Add Spotlight Integration (Priority: 6/10, Effort: 6h)

**Impact:** System search for Jarvis commands

**Files to Modify:**

- Create: `JarvisApp/Sources/JarvisApp/Services/SpotlightService.swift`
- Create: `JarvisApp/Sources/JarvisApp/Utils/CoreSpotlightExtensions.swift`

**Implementation Steps:**

1. Index recent commands in Spotlight

```swift
import CoreSpotlight
import MobileCoreServices

func indexCommand(_ command: String, description: String) {
    let attributeSet = CSSearchableItemAttributeSet(itemContentType: kUTTypeText as String)
    attributeSet.title = command
    attributeSet.contentDescription = description
    attributeSet.keywords = [command, "jarvis"]

    let item = CSSearchableItem(uniqueIdentifier: command, domainIdentifier: "com.jarvis.commands", attributeSet: attributeSet)
    CSSearchableIndex.default().indexSearchableItems([item])
}
```

1. Handle Spotlight callbacks

```swift
// In JarvisApp.swift
.onContinueUserActivity(CSSearchableItemActionType, perform: { userActivity in
    if let identifier = userActivity.userInfo?[CSSearchableItemActivityIdentifier] as? String {
        // Execute command
    }
})
```

**Dependencies:** None

**Success Metrics:**

- Commands appear in Spotlight
- Launching from Spotlight works
- Recent commands indexed

---

### T2.7 Add Unit and UI Tests (Priority: 7/10, Effort: 10h)

**Impact:** Catch regressions, confident refactoring

**Files to Modify:**

- Create: `JarvisApp/Tests/JarvisAppTests/*.swift`

**Implementation Steps:**

1. Add tests for models

```swift
// ContainerInfoTests.swift
import XCTest
@testable import JarvisApp

final class ContainerInfoTests: XCTestCase {
    func testStatusColorMapping() {
        let container = ContainerInfo(
            id: "1", name: "test", status: "running",
            image: "test:latest", cpus: 2, memory: "512MB", taskId: nil
        )
        XCTAssertEqual(container.statusColor, .green)
    }
}
```

1. Add tests for ViewModels

```swift
// CommandCenterViewModelTests.swift
func testLoadContainers() async throws {
    let viewModel = CommandCenterViewModel()
    await viewModel.loadContainers()
    XCTAssertFalse(viewModel.isLoading)
    XCTAssertFalse(viewModel.containers.isEmpty)
}
```

1. Add UI tests

```swift
// JarvisUITests.swift
func testApprovalFlow() throws {
    let app = XCUIApplication()
    app.launch()
    // Test approval interaction
}
```

**Dependencies:** T2.2

**Success Metrics:**
>
- >70% code coverage
- All critical paths tested
- Tests pass in CI

---

## Tier 3: Long-Term (1+ months)

### T3.1 Implement Swift Native Daemon (Priority: 7/10, Effort: 80h)

**Impact:** Single binary, better performance

**Files to Modify:**

- Create: New Xcode project for native daemon
- Migrate: Python daemon logic to Swift

**Implementation Steps:**

1. Create native Swift daemon using AsyncWebSocket
2. Implement container management using Docker API directly
3. Use OSLog for logging
4. Create launchd configuration for native daemon
5. Migrate orchestrator logic or keep Python subprocess

**Architecture Decision:**

- Option A: Full Swift rewrite (80h)
- Option B: Hybrid - Swift daemon + Python subprocess (40h)

**Dependencies:** T2.1

**Success Metrics:**

- Daemon runs as native Swift process
- Memory usage <50MB
- Startup time <1s

---

### T3.2 Build iOS Companion App (Priority: 6/10, Effort: 60h)

**Impact:** Mobile access, remote monitoring

**Files to Modify:**

- Create: New iOS app target
- Share: Code via multi-platform framework

**Implementation Steps:**

1. Create SwiftUI framework for shared code

```swift
// JarvisKit framework
// - Models
// - WebSocket protocol
// - ViewModels
```

1. Build iOS app with:

- Remote notifications
- TouchID/FaceID for approvals
- Compact mobile UI
- Background sync

1. Add App Groups for data sharing

**Dependencies:** T2.2, T2.3

**Success Metrics:**

- iOS app approved
- Remote approvals work
- Syncs with Mac app

---

### T3.3 Implement Siri Integration (Priority: 5/10, Effort: 40h)

**Impact:** Voice commands, hands-free operation

**Files to Modify:**

- Create: `JarvisApp/Sources/JarvisApp/Intents/*.swift`

**Implementation Steps:**

1. Create Intents extension

```swift
// RunTaskIntent.swift
import Intents

class RunTaskIntent: INIntent {
    var taskDescription: String?
}

class RunTaskIntentHandler: NSObject, RunTaskIntentHandling {
    func handle(intent: RunTaskIntent) async -> RunTaskIntentResponse {
        // Execute task via WebSocket
    }
}
```

1. Define Siri phrases
2. Handle voice responses

**Dependencies:** T3.1

**Success Metrics:**

- "Hey Siri, run tests in Jarvis" works
- Voice feedback for status

---

### T3.4 Implement CloudKit Sync (Priority: 5/10, Effort: 40h)

**Impact:** Multi-device sync, backup

**Files to Modify:**

- Create: `JarvisApp/Sources/JarvisApp/Services/CloudKitService.swift`

**Implementation Steps:**

1. Sync timeline events to CloudKit
2. Sync approvals across devices
3. Backup configuration
4. Handle merge conflicts

**Dependencies:** T2.3, T3.2

**Success Metrics:**

- Timeline syncs to iOS
- Approvals propagate
- No data loss on reinstall

---

### T3.5 Create Widget Extension (Priority: 6/10, Effort: 20h)

**Impact:** At-a-glance status, quick actions

**Files to Modify:**

- Create: Widget extension target

**Implementation Steps:**

1. Create status widget

```swift
struct JarvisStatusWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "JarvisStatus", provider: JarvisStatusProvider()) { entry in
            JarvisStatusWidgetView(entry: entry)
        }
        .configurationDisplayName("Jarvis Status")
        .description("Shows Jarvis running state")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}
```

1. Add quick actions widget
2. Implement timeline widget

**Dependencies:** T2.3

**Success Metrics:**

- Status shows on lock screen
- Quick actions work from widget
- Updates every 15min

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Python daemon migration complexity | High | High | Keep hybrid approach, gradual migration |
| iOS app approval delays | Medium | Medium | Follow guidelines, prepare early |
| Breaking changes in macOS APIs | Low | Medium | Use stable APIs, test on betas |
| Performance degradation | Low | High | Profile before/after, set benchmarks |
| User adoption friction | Low | Low | Maintain existing UI, additive features |

---

## Implementation Order

**Week 1-2: Foundation (Quick Wins)**

- T1.1: Fix critical Swift issues
- T1.2: Separate view logic from models
- T1.3: Add accessibility support
- T1.4: Create shared EventColors utility
- T1.5: Add loading/error states

**Week 3-4: Core Improvements**

- T1.6: Add native notifications
- T1.7: Create design system
- T2.1: Implement proper WebSocket protocol
- T2.2: Implement MVVM architecture

**Week 5-8: Enhanced Features**

- T2.3: Add local persistence
- T2.4: Add menu bar native features
- T2.5: Implement better error handling
- T2.6: Add Spotlight integration
- T2.7: Add unit and UI tests

**Month 3+: Major Features (parallel tracks)**

- T3.1: Swift native daemon (infrastructure track)
- T3.2: iOS companion app (mobile track)
- T3.3: Siri integration (optional)
- T3.4: CloudKit sync (optional)
- T3.5: Widget extension (optional)

---

## Success Metrics

### Technical Metrics

- 90%+ test coverage for critical paths
- <500ms cold start time
- <50MB memory footprint (menu bar app)
- <1s WebSocket reconnection time
- Zero crash incidents in production

### User Experience Metrics

- VoiceOver compatibility for all features
- <3 clicks to any common action
- Clear error messages for all failures
- Offline capability for cached data

### Developer Experience Metrics

- Build time <30s
- Clean architecture (MVVM compliance)
- No SwiftUI imports in models
- Mockable protocols for networking

---

## Recommended Next Steps

1. **Start with T1.1** - Fix critical issues preventing reliable operation
2. **Create feature branch** for Tier 1 work
3. **Set up CI/CD** for automated testing
4. **Establish code review process** for Swift changes
5. **Document architectural decisions** in ADRs

---

## Appendix: File Structure After Implementation

```
JarvisApp/
├── Sources/
│   └── JarvisApp/
│       ├── JarvisApp.swift          # App entry point
│       ├── Models/                  # Pure data models
│       │   ├── ContainerInfo.swift
│       │   ├── TimelineEvent.swift
│       │   └── JarvisStatus.swift
│       ├── ViewModels/              # MVVM view models
│       │   ├── CommandCenterViewModel.swift
│       │   ├── TimelineViewModel.swift
│       │   └── ApprovalViewModel.swift
│       ├── Views/                   # SwiftUI views
│       │   ├── JarvisMenuView.swift
│       │   ├── CommandCenterView.swift
│       │   ├── TimelineView.swift
│       │   └── ApprovalView.swift
│       ├── Services/                # Business logic
│       │   ├── WebSocketService.swift
│       │   ├── PersistenceService.swift
│       │   └── NotificationService.swift
│       ├── Utils/                   # Utilities
│       │   ├── DesignSystem.swift
│       │   ├── EventColors.swift
│       │   ├── ViewExtensions.swift
│       │   └── ErrorHandler.swift
│       └── Protocols/               # Protocol definitions
│           └── WebSocketProtocol.swift
├── Tests/
│   ├── JarvisAppTests/
│   │   ├── ModelTests/
│   │   ├── ViewModelTests/
│   │   └── ServiceTests/
│   └── JarvisAppUITests/
└── Package.swift
```

---

*Document Version: 1.0*
*Last Updated: 2025-02-11*
*Author: Integration Architect*
