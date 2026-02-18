//
//  DashboardView.swift
//  JarvisiOSApp
//
//  Mobile-optimized dashboard showing Jarvis status
//

import SwiftUI

struct DashboardView: View {
    @State private var isConnected = false
    @State private var activeTasks = 0
    @State private var pendingApprovals = 0
    @State private var lastUpdate = Date()

    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 20) {
                    // Connection Status Card
                    StatusCard(
                        title: "Connection",
                        value: isConnected ? "Connected" : "Disconnected",
                        color: isConnected ? .green : .red,
                        icon: isConnected ? "wifi" : "wifi.slash"
                    )

                    // Active Tasks Card
                    StatusCard(
                        title: "Active Tasks",
                        value: "\(activeTasks)",
                        color: .blue,
                        icon: "gearshape.2"
                    )

                    // Pending Approvals Card
                    StatusCard(
                        title: "Pending Approvals",
                        value: "\(pendingApprovals)",
                        color: pendingApprovals > 0 ? .orange : .gray,
                        icon: "hand.raised"
                    )

                    // Last Update
                    Text("Last update: \(lastUpdate, style: .time)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .padding()
            }
            .navigationTitle("Jarvis Dashboard")
            .refreshable {
                await refreshData()
            }
        }
    }

    private func refreshData() async {
        // Simulate data refresh
        try? await Task.sleep(nanoseconds: 500_000_000)
        lastUpdate = Date()
    }
}

struct StatusCard: View {
    let title: String
    let value: String
    let color: Color
    let icon: String

    var body: some View {
        HStack {
            Image(systemName: icon)
                .font(.title2)
                .foregroundStyle(color)
                .frame(width: 40)

            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text(value)
                    .font(.headline)
            }

            Spacer()
        }
        .padding()
        .background(color.opacity(0.1))
        .cornerRadius(12)
    }
}

#Preview {
    DashboardView()
}
