// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "JarvisClient",
    platforms: [
        .macOS(.v14),
        .iOS(.v17),
    ],
    products: [
        .library(
            name: "JarvisClient",
            targets: ["JarvisClient"]
        ),
    ],
    dependencies: [
        .package(url: "https://github.com/daltoniam/Starscream", from: "4.0.0"),
    ],
    targets: [
        .target(
            name: "JarvisClient",
            dependencies: [
                .product(name: "Starscream", package: "Starscream"),
            ],
            path: "Sources/JarvisClient"
        ),
    ]
)
