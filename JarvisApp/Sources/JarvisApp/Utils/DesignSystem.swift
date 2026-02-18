import SwiftUI

struct DesignSystem {
    // MARK: - Spacing
    struct Spacing {
        static let xs: CGFloat = 4
        static let sm: CGFloat = 8
        static let md: CGFloat = 12
        static let lg: CGFloat = 16
        static let xl: CGFloat = 24
        static let xxl: CGFloat = 32
    }

    // MARK: - Colors
    struct Colors {
        // Status colors
        static let statusRunning = Color.green
        static let statusStopped = Color.red
        static let statusPaused = Color.yellow
        static let statusError = Color.red

        // Semantic colors (use system colors)
        static let background = Color(.windowBackgroundColor)
        static let secondaryBackground = Color(.controlBackgroundColor)
        static let text = Color(.labelColor)
        static let secondaryText = Color(.secondaryLabelColor)
        static let accent = Color.accentColor
    }

    // MARK: - Typography
    struct Typography {
        static let largeTitle = Font.largeTitle
        static let title = Font.title
        static let title2 = Font.title2
        static let title3 = Font.title3
        static let headline = Font.headline
        static let subheadline = Font.subheadline
        static let body = Font.body
        static let callout = Font.callout
        static let footnote = Font.footnote
        static let caption = Font.caption
        static let caption2 = Font.caption2
    }

    // MARK: - Layout
    struct Layout {
        static let menuBarWidth: CGFloat = 420
        static let menuBarHeight: CGFloat = 520
        static let contentHeight: CGFloat = 320
        static let timelineHeight: CGFloat = 300
        static let minHeight: CGFloat = 200
    }

    // MARK: - Corner Radius
    struct CornerRadius {
        static let small: CGFloat = 4
        static let medium: CGFloat = 6
        static let large: CGFloat = 8
        static let xlarge: CGFloat = 12
    }

    // MARK: - Icon Sizes
    struct IconSize {
        static let xs: CGFloat = 8
        static let sm: CGFloat = 10
        static let md: CGFloat = 12
        static let lg: CGFloat = 16
    }
}

// MARK: - View Modifiers
extension View {
    func standardPadding() -> some View {
        padding(.horizontal, DesignSystem.Spacing.lg)
            .padding(.vertical, DesignSystem.Spacing.md)
    }

    func cardStyle() -> some View {
        background(Color.secondary.opacity(0.1))
            .cornerRadius(DesignSystem.CornerRadius.medium)
    }
}
