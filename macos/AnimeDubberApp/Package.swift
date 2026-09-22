// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "AnimeDubberApp",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(name: "AnimeDubberApp", targets: ["AnimeDubberApp"])
    ],
    targets: [
        .executableTarget(
            name: "AnimeDubberApp",
            path: "Sources/AnimeDubberApp",
            linkerSettings: [
                .linkedFramework("Security")
            ]
        )
    ]
)
