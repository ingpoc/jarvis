// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "JarvisApp",
    platforms: [.macOS(.v14)],
    dependencies: [
        .package(path: "../JarvisClient"),
    ],
    targets: [
        .executableTarget(
            name: "JarvisApp",
            dependencies: [
                .product(name: "JarvisClient", package: "JarvisClient"),
            ],
            path: "Sources/JarvisApp"
        ),
    ]
)
