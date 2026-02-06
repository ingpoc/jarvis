import SwiftUI

#if os(iOS)
import UIKit
typealias PlatformImage = UIImage
#elseif os(macOS)
import AppKit
typealias PlatformImage = NSImage
#endif

extension View {
    @ViewBuilder
    func optionalListStyle() -> some View {
        #if os(iOS)
        self.listStyle(.insetGrouped)
        #else
        self.listStyle(.inset)
        #endif
    }

    @ViewBuilder
    func optionalIndexViewStyle() -> some View {
        #if os(iOS)
        self.indexViewStyle(.page(backgroundDisplayMode: .always))
        #else
        self
        #endif
    }

    @ViewBuilder
    func optionalNavigationBarTitleDisplayMode() -> some View {
        #if os(iOS)
        self.navigationBarTitleDisplayMode(.inline)
        #else
        self
        #endif
    }
}
