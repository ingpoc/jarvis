# JarvisiOS

iPhone app for remote Jarvis control.

## Setup

This is a SwiftUI iOS app project. To set up in Xcode:

1. Open Xcode
2. File → New → Project
3. Choose "iOS App" under App
4. Product Name: JarvisiOS
5. Interface: SwiftUI
6. Language: Swift
7. Save to: jarvis-mac/JarvisiOS/

## Dependencies

Add the JarvisClient package:

- File → Add Package Dependencies
- Add: `../JarvisClient`

## Views

The iOS app shares 80% of views with Mac app, adapted for mobile:

- `DashboardView.swift` - Mobile-optimized dashboard
- `TimelineView.swift` - Touch-friendly event list
- `CommandView.swift` - Mobile command input
- `VoiceView.swift` - Push-to-talk with haptic feedback
- `SettingsView.swift` - iOS-style settings with Face ID

## iOS-Specific Features

- Background audio recording for voice
- Push notifications (APNs)
- Face ID / Touch ID for app lock
- Haptic feedback on actions
- Optimized layout for smaller screens
- Pull-to-refresh on timeline
- Swipe actions on events
