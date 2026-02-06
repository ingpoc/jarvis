import SwiftUI

#if os(iOS)
import UIKit
typealias PlatformColor = UIColor
#elseif os(macOS)
import AppKit
typealias PlatformColor = NSColor
#endif

extension PlatformColor {
    static var systemGroupedBackground: PlatformColor {
        #if os(iOS)
        return UIColor.systemGroupedBackground
        #elseif os(macOS)
        return NSColor.controlBackgroundColor
        #endif
    }

    static var secondarySystemGroupedBackground: PlatformColor {
        #if os(iOS)
        return UIColor.secondarySystemGroupedBackground
        #elseif os(macOS)
        return NSColor.unemphasizedSelectedContentBackgroundColor
        #endif
    }
}
