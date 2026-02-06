import SwiftUI

struct OnboardingView: View {
    @Binding var isPresented: Bool
    let onComplete: () -> Void

    @State private var currentPage = 0

    var body: some View {
        TabView(selection: $currentPage) {
            OnboardingPage(
                icon: "brain.head.profile",
                title: "Meet Jarvis",
                description: "Your autonomous development partner, now in your pocket.",
                action: {
                    Button("Continue") { currentPage = 1 }
                }
            )

            OnboardingPage(
                icon: "waveform",
                title: "Voice Control",
                description: "Give commands naturally. Jarvis understands context.",
                action: {
                    Button("Continue") { currentPage = 2 }
                }
            )

            OnboardingPage(
                icon: "gearshape.fill",
                title: "Get Started",
                description: "Pair with your Jarvis server to begin.",
                action: {
                    Button("Pair Now") {
                        onComplete()
                    }
                    .buttonStyle(.primaryButtonStyle())
                }
            )
        }
        .optionalIndexViewStyle()
        .ignoresSafeArea(.keyboard)
    }
}

struct OnboardingPage: View {
    let icon: String
    let title: String
    let description: String
    let action: () -> Void

    var body: some View {
        VStack(spacing: 32) {
            Spacer()

            Image(systemName: icon)
                .font(.system(size: 72))
                .foregroundStyle(accentColor)

            VStack(spacing: 12) {
                Text(title)
                    .font(.system(size: 28, weight: .bold))

                Text(description)
                    .font(.system(size: 16))
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            }

            Spacer()

            action()
        }
        .padding()
    }

    private var accentColor: Color {
        #if os(iOS)
        return .accentColor
        #else
        return .blue
        #endif
    }
}
