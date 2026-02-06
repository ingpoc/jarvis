// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "JarvisApp",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(
            name: "JarvisApp",
            path: "Sources/JarvisApp"
        ),
    ]
)
