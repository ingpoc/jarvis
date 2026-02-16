import XCTest
@testable import JarvisApp

// MARK: - ContainerInfo Tests

final class ContainerInfoTests: XCTestCase {
    func testContainerInitialization() {
        let container = ContainerInfo(
            id: "container-1",
            name: "test-container",
            status: "running",
            image: "test:latest",
            cpus: 2,
            memory: "512MB",
            taskId: "task-1"
        )

        XCTAssertEqual(container.id, "container-1")
        XCTAssertEqual(container.name, "test-container")
        XCTAssertEqual(container.status, "running")
        XCTAssertEqual(container.image, "test:latest")
        XCTAssertEqual(container.cpus, 2)
        XCTAssertEqual(container.memory, "512MB")
        XCTAssertEqual(container.taskId, "task-1")
    }

    func testContainerStatusColors() {
        // Test running container
        let running = ContainerInfo(
            id: "1", name: "test", status: "running",
            image: "test", cpus: 1, memory: "512MB", taskId: nil
        )
        XCTAssertEqual(running.statusColor, .green)

        // Test stopped container
        let stopped = ContainerInfo(
            id: "2", name: "test", status: "stopped",
            image: "test", cpus: 1, memory: "512MB", taskId: nil
        )
        XCTAssertEqual(stopped.statusColor, .red)

        // Test paused container
        let paused = ContainerInfo(
            id: "3", name: "test", status: "paused",
            image: "test", cpus: 1, memory: "512MB", taskId: nil
        )
        XCTAssertEqual(paused.statusColor, .yellow)
    }

    func testContainerStatusIcons() {
        let running = ContainerInfo(
            id: "1", name: "test", status: "running",
            image: "test", cpus: 1, memory: "512MB", taskId: nil
        )
        XCTAssertEqual(running.statusIcon, "checkmark.circle.fill")

        let stopped = ContainerInfo(
            id: "2", name: "test", status: "stopped",
            image: "test", cpus: 1, memory: "512MB", taskId: nil
        )
        XCTAssertEqual(stopped.statusIcon, "xmark.circle.fill")
    }
}
