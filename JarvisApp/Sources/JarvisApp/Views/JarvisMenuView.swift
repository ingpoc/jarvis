import SwiftUI
import JarvisClient

struct JarvisMenuView: View {
    @Environment(\.openWindow) private var openWindow
    @Environment(AuthManager.self) private var auth

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header with status
            HStack {
                Circle()
                    .fill(Color.green)
                    .frame(width: 8, height: 8)

                Text("Jarvis Ready")
                    .font(.system(size: 12))

                Spacer()
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)

            Divider()

            // Open window button
            Button {
                openWindow(id: "main-window")
            } label: {
                HStack {
                    Image(systemName: "doc.text.fill")
                    Text("Open Jarvis")
                    Spacer()
                }
                .font(.system(size: 13))
                .foregroundStyle(.primary)
            }
            .buttonStyle(.plain)
            .padding(.horizontal, 12)
            .padding(.vertical, 6)

            Divider()

            // Quick status
            HStack {
                Text("Connected")
                    .font(.system(size: 11))
                Spacer()
                Circle()
                    .fill(Color.green)
                    .frame(width: 6, height: 6)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)

            Divider()

            // Quit
            Button {
                NSApplication.shared.terminate(nil)
            } label: {
                HStack {
                    Image(systemName: "xmark")
                    Text("Quit")
                }
                .font(.system(size: 11))
                .foregroundStyle(.red)
            }
            .buttonStyle(.plain)
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
        }
        .frame(width: 200)
    }
}
