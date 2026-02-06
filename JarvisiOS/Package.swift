// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "JarvisiOS",
    platforms: [
        .iOS(.v17),
        .macOS(.v14),
    ],
    products: [
        .library(
            name: "JarvisiOS",
            targets: ["JarvisiOS"]
        ),
    ],
    dependencies: [
        .package(path: "../JarvisClient"),
    ],
    targets: [
        .target(
            name: "JarvisiOS",
            dependencies: [
                "JarvisClient",
            ],
            path: "Sources/JarvisiOS"
        ),
    ]
)
