// swift-tools-version: 6.0
// Caixa's helper for Apple Intelligence (Apple's on-device Foundation Models). See README.md.
import PackageDescription

let package = Package(
    name: "caixa-apple-intelligence",
    platforms: [.macOS("26.0")],
    targets: [
        .executableTarget(
            name: "caixa-apple-intelligence",
            path: "Sources/caixa-apple-intelligence"
        )
    ],
    swiftLanguageModes: [.v5]
)
