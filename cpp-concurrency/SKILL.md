---
name: cpp-concurrency
description: Decisions, pitfalls, and patterns for multi-threaded C++ — thread lifecycle, synchronization, lock-free structures, and concurrent architecture. Use when writing, reviewing, or debugging multi-threaded C++ code involving std::thread/jthread, mutex/atomic/condition_variable, producer-consumer queues, thread pools, memory ordering, data races, or deadlocks. Also use when the user asks "is this thread-safe", wants a concurrency code review, encounters a race condition or hang, or is designing any class/system accessed from multiple threads — even if they don't explicitly mention concurrency.
---

# C++ Concurrency

## How to Use

1. Use the decision tree to pick **one** reference — read only that file.
2. If the task spans two areas (e.g., synchronization + architecture), read the second on demand.
3. **Writing** concurrent code: default to jthread + scoped_lock; verify every shared mutable variable has synchronization and every long-running thread has a shutdown path.
4. **Reviewing** concurrent code: trace each shared mutable variable — who reads, who writes, what synchronizes them. Use [review-checklist.md](references/review-checklist.md) as a systematic pass.
5. **Debugging** a race or deadlock: reproduce → isolate the shared state → apply tooling (TSan, Concurrency Visualizer) → verify fix under stress.
6. **Non-std threading** (Boost.Asio, Qt threads, Win32 thread pool, etc.): the core rules and review checklist still apply — map them to the framework's primitives rather than copying std:: code verbatim.

## References

| Category | When to Use | Reference |
|----------|------------|-----------|
| **Threads & Async** | thread/jthread lifecycle, async, future/promise, passing data to threads | [thread-and-async.md](references/thread-and-async.md) |
| **Synchronization** | mutex, scoped_lock, condition_variable, shared_mutex, atomic vs lock | [synchronization.md](references/synchronization.md) |
| **Patterns & Architecture** | Producer-consumer queue, thread pool, active object | [patterns-and-architecture.md](references/patterns-and-architecture.md) |
| **Thread Safety Patterns** | Cancellation, UI/worker boundary, callback lifetime, singleton | [thread-safety-patterns.md](references/thread-safety-patterns.md) |
| **Memory Ordering** | acquire/release, lock-free structures, relaxed vs seq_cst | [memory-ordering.md](references/memory-ordering.md) |
| **Review Checklist** | Systematic check for data race, deadlock, dangling capture, missing cancel | [review-checklist.md](references/review-checklist.md) |

## Core Rules

1. **Every `std::thread` must be joined or detached** — an unjoinable thread's destructor calls `std::terminate()`. Prefer `std::jthread` which auto-joins.
2. **Never access shared data without synchronization** — without a mutex, atomic, or immutability guarantee, the compiler and CPU may reorder or tear reads/writes across threads.
3. **Lock ordering must be consistent** — if thread A locks X then Y, and thread B locks Y then X, you deadlock. Use `scoped_lock(X, Y)` or enforce a documented global order.
4. **Prefer `scoped_lock` over manual lock/unlock** — manual lock/unlock leaks on exceptions and early returns. RAII locks make "forget to unlock" impossible.
5. **`std::atomic` ≠ thread-safe class** — people see "atomic" and assume the whole object is safe, but atomics only protect a single value. Two atomic fields can be individually consistent yet mutually contradictory — use a mutex when an invariant spans multiple fields.
6. **Callbacks captured by reference + async = dangling** — the lambda outlives the captured object. Capture by value or use `shared_ptr` / `shared_from_this`.
7. **Every long-running thread needs a stop mechanism** — without one, the thread blocks shutdown and leaks resources. Use `stop_token`, an atomic flag, or a closeable queue.

