# Testing & Debugging

## Table of Contents
1. Stress Harness
2. Sanitizer Strategy
3. Hang and Deadlock Triage
4. Logging and Observability

---

## 1. Stress Harness

Concurrency fixes need repeated execution, forced interleavings, and clear failure signals.

```cpp
TEST(Queue, StressPushPop) {
    BlockingQueue<int> q(256);
    std::atomic<bool> failed = false;

    std::jthread producer([&] {
        for (int i = 0; i < 100000; ++i) {
            if (!q.push(i)) failed.store(true, std::memory_order_relaxed);
        }
        q.close();
    });

    std::jthread consumer([&] {
        int expected = 0;
        while (auto item = q.pop()) {
            if (*item != expected++) {
                failed.store(true, std::memory_order_relaxed);
                return;
            }
        }
    });

    ASSERT_FALSE(failed.load());
}
```

Guidelines:
- Run the test in a loop to amplify rare races.
- Add short sleeps or yields only when trying to widen a suspected race window.
- Assert on invariants, not just "program did not crash".

---

## 2. Sanitizer Strategy

| Tool | Best For | Notes |
|------|----------|-------|
| Thread Sanitizer | Data races | Best first pass on Clang/GCC builds |
| Address Sanitizer | Use-after-free from async lifetime bugs | Valuable when callbacks capture dead objects |
| Undefined Behavior Sanitizer | Overflow, invalid atomics assumptions, UB around indices | Good companion to TSan/ASan |

Use TSan on minimized, deterministic reproductions first. If the full app is too noisy, carve out the queue, worker, or state machine into a dedicated stress test.

---

## 3. Hang and Deadlock Triage

When a test or app hangs:

1. Identify which thread is waiting and on what primitive.
2. Check whether the wake-up predicate can ever become true.
3. Check whether shutdown can reach blocked waits.
4. Dump all thread stacks before changing code.

Typical patterns:
- Thread blocked in `cv.wait(...)` but predicate ignores shutdown.
- Two threads each holding one mutex and waiting for the other.
- UI thread blocked on `future.get()` while worker waits for UI work.
- Queue drained, but producer never signals closure, so consumers wait forever.

Windows-specific tools:
- Visual Studio Concurrency Visualizer for contention and wait analysis
- Wait Chain Traversal / debugger thread stacks for deadlock graphs

---

## 4. Logging and Observability

For concurrency bugs, logs must reconstruct ordering, not just events.

Include:
- Thread id or logical worker name
- Object/request id to correlate cross-thread work
- State transitions before and after each synchronization point
- Queue size or backlog when diagnosing starvation

Avoid logging while holding hot locks unless the logger is designed for it; otherwise the diagnostics change the timing enough to hide the bug.
