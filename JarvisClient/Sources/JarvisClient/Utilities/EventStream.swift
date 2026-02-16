import Foundation
import Combine

/// Async event stream for TimelineEvent updates
@available(macOS 14, iOS 17, *)
public final class EventStream: Sendable {
    private let continuation: AsyncStream<TimelineEvent>.Continuation
    public let stream: AsyncStream<TimelineEvent>

    public init() {
        var cont: AsyncStream<TimelineEvent>.Continuation?
        self.stream = AsyncStream { cont = $0 }
        self.continuation = cont!
    }

    public func emit(_ event: TimelineEvent) {
        continuation.yield(event)
    }

    public func complete() {
        continuation.finish()
    }
}

/// Time-based event filter
public struct EventFilter {
    public let eventTypes: Set<String>?
    public let minTimestamp: Double?
    public let maxTimestamp: Double?
    public let limit: Int?

    public init(
        eventTypes: Set<String>? = nil,
        minTimestamp: Double? = nil,
        maxTimestamp: Double? = nil,
        limit: Int? = nil
    ) {
        self.eventTypes = eventTypes
        self.minTimestamp = minTimestamp
        self.maxTimestamp = maxTimestamp
        self.limit = limit
    }

    public func matches(_ event: TimelineEvent) -> Bool {
        if let types = eventTypes, !types.contains(event.eventType) {
            return false
        }
        if let min = minTimestamp, event.timestamp < min {
            return false
        }
        if let max = maxTimestamp, event.timestamp > max {
            return false
        }
        return true
    }
}
