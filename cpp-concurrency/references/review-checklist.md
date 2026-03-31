# Concurrent Code Review Checklist

Systematic pass for reviewing or writing multi-threaded code. For each item: what to look for, the red flag, and where the fix lives.

---

## 1. Data Race

**Trace:** For every shared mutable variable, list all access points. At least one writes? Then there must be a mutex, atomic, or immutability guarantee covering every access.

| Red Flag | Example | Fix (see synchronization.md) |
|----------|---------|-----|
| Bare `int`/`struct` accessed from multiple threads | `counter++` from two threads | `std::atomic<int>` or mutex |
| Container modified while iterated | `vec.push_back()` + range-for concurrently | Lock, or copy-on-read |
| Struct with multi-field invariant protected by atomics alone | Two `atomic<int>` fields that must be consistent | Single mutex covering both |

**Tooling:**

```bash
# Clang/GCC: Thread Sanitizer
clang++ -fsanitize=thread -g -O1 main.cpp -o main && ./main

# MSVC: no TSan — use Application Verifier or Concurrency Visualizer
```

---

## 2. Deadlock

**Trace:** Find every site that holds 2+ locks simultaneously. Are they always acquired in the same order?

| Red Flag | Fix (see synchronization.md §4) |
|----------|-----|
| Two functions lock A,B and B,A respectively | `std::scoped_lock(A, B)` or documented ordering |
| Lock held during callback / virtual call | Copy data out, release lock, then call |
| Lock held when calling into another module | Same — minimize scope under lock |

---

## 3. Dangling Callback / Capture

**Trace:** For every lambda posted to another thread, check: can the captured object be destroyed before the lambda runs?

| Red Flag | Fix (see thread-safety-patterns.md §3) |
|----------|-----|
| `[this]` + `detach()` or `async` | `shared_from_this`, or own the thread as a member |
| `[&local_var]` + `detach()` | Move data into lambda: `[data = std::move(data)]` |
| `weak_ptr::lock()` result used without null check | `if (auto sp = wp.lock()) { sp->use(); }` |

---

## 4. UI Thread Violation

**Trace:** Any UI object (`HWND`, widget pointer, label) touched from a non-UI thread?

| Red Flag | Fix (see thread-safety-patterns.md §2) |
|----------|-----|
| `label->set_text()` from worker thread | Marshal via `PostMessage`, `dispatch_async`, or dispatcher queue |
| `future.get()` on UI thread | Non-blocking poll, or post result back to UI thread |

---

## 5. Missing Stop Mechanism

**Trace:** Every long-running or looping thread — can it be told to stop?

| Red Flag | Fix (see thread-safety-patterns.md §1) |
|----------|-----|
| `while (true)` with no exit condition | `while (!stoken.stop_requested())` |
| Blocking I/O with no timeout or interrupt | `stop_callback` to cancel I/O, or timed waits |
| Stop flag checked too infrequently | Check each iteration, not after entire batch |

---

## 6. Thread Lifetime

**Trace:** Every `std::thread` / `std::jthread` — who joins it? When?

| Red Flag | Fix (see thread-and-async.md §5) |
|----------|-----|
| `thread.detach()` | Almost always wrong — use `jthread` as member |
| Thread not joined before data it accesses is destroyed | Declare thread member AFTER data members (reverse destruction order) |
| Orphaned thread with no owner | Store in a member or pool |

---

## Quick Summary

| Check | Key Question | Red Flag |
|-------|-------------|----------|
| Data race | Is shared mutable state synchronized? | No mutex/atomic |
| Deadlock | Multiple locks — consistent order? | Inconsistent ordering, lock during callback |
| Dangling capture | Does lambda outlive captured object? | `[this]`/`[&]` with detach/async |
| UI from worker | UI code on non-UI thread? | Direct widget access from worker |
| Missing cancel | Can this thread be stopped? | `while(true)`, infinite blocking |
| Thread lifetime | Who joins? When? | Orphaned thread, no join/detach |

## Debugging Tools

| Tool | Detects | Platform |
|------|---------|----------|
| Thread Sanitizer (`-fsanitize=thread`) | Data races | GCC, Clang |
| Helgrind / DRD (Valgrind) | Data races, deadlocks | Linux |
| Application Verifier | Lock issues, heap corruption | Windows |
| Concurrency Visualizer | Contention, utilization | Windows (VS) |
| Intel Inspector | Data races, deadlocks | Cross-platform |
