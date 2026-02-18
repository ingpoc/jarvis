//
//  ContentView.swift
//  JarvisiOSApp
//
//  Main tab-based interface
//

import SwiftUI

struct ContentView: View {
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            DashboardView()
                .tabItem {
                    Label("Dashboard", systemImage: "chart.line.uptrend.xyaxis")
                }
                .tag(0)

            TimelineView()
                .tabItem {
                    Label("Timeline", systemImage: "clock")
                }
                .tag(1)

            CommandView()
                .tabItem {
                    Label("Commands", systemImage: "terminal")
                }
                .tag(2)
        }
        .tint(.blue)
    }
}

#Preview {
    ContentView()
}
