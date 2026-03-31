# Advanced Lock-Free

## Table of Contents
1. Scope and Default Stance
2. atomic::wait / notify_*
3. ABA Hazards
4. Memory Reclamation
5. MPMC Queue Boundaries
6. Review Heuristics

---

## 1. Scope and Default Stance

Use this file only when the task is genuinely about lock-free or low-lock coordination. For most product code, a mutex, sharded locking, or a blocking queue is the better default.

Red flags that justify reading this file:
- CAS loops on pointers or linked nodes
- Custom queue/stack/free-list implementations
- Requirements like "no kernel wait", "very high contention", or "single-digit microsecond latency"
- Existing code already uses lock-free structures and needs review or debugging

Default stance: prefer proven libraries or a simpler blocking design unless profiling shows synchronization is the bottleneck. Treat memory reclamation as part of correctness, not a later optimization.

---

## 2. atomic::wait / notify_*

`std::atomic::wait` and `notify_*` are useful when the state already lives in an atomic and the waiter only needs to sleep until that value changes.

### Good fit

- One atomic flag/state variable controls progress
- Wait condition is equality on that atomic value
- You want to avoid a separate mutex + condition_variable pair

### Not a good fit

- Wake condition depends on multiple fields or a compound invariant
- You need a protected critical section after wake-up
- The shared state is not already atomic

### Pattern: state transition + wait

```cpp
std::atomic<State> state{State::idle};

void producer() {
    publish_work();
    state.store(State::ready, std::memory_order_release);
    state.notify_one();
}

void consumer() {
    State expected = State::idle;
    while ((expected = state.load(std::memory_order_acquire)) == State::idle) {
        state.wait(State::idle, std::memory_order_relaxed);
    }
    consume_work();  // Sees writes published before the release store
}
```

Guidelines:
- Store the new value before `notify_*`.
- Use release on the publishing store and acquire on the consuming load when other memory must become visible.
- Recheck in a loop after wake-up; `wait` is value-based, not "the work is definitely done".

Rule of thumb:
- Single atomic state and simple wake-up -> `atomic::wait`
- Complex predicate or multiple fields -> `condition_variable`

---

## 3. ABA Hazards

ABA happens when a CAS checks "this pointer/value is still A", but the location changed from A -> B -> A in the meantime. The CAS succeeds even though the underlying object history changed.

Typical places:
- Treiber stack
- Lock-free free lists
- Intrusive linked structures with node reuse

### Why it matters

If nodes can be removed, reused, and reinserted, pointer equality alone does not prove the structure is unchanged. The result can be corruption, lost nodes, or use-after-free.

### Mitigations

- Tagged/versioned pointers
- Hazard pointers
- Epoch-based reclamation
- Avoid immediate node reuse

### Guidance for review

- If CAS operates on node pointers, ask "what prevents ABA?"
- If the answer is "the allocator usually won't reuse that fast", treat it as a bug.
- If the code has no reclamation strategy, assume pointer-based lock-free structures are unsafe until proven otherwise.

---

## 4. Memory Reclamation

Lock-free containers are often harder to reclaim safely than to push/pop correctly.

### Hazard pointers

Use when threads need to publish "I am currently reading this node; do not free it yet".

Tradeoffs:
- Precise protection for individual nodes
- Higher per-access overhead
- More implementation complexity and bookkeeping

Good fit:
- Pointer-heavy structures with long or irregular reader lifetimes
- Need to reclaim memory without global quiescent points

### Epoch reclamation

Use when threads progress through quiescent periods and retired nodes can be freed only after all active threads have advanced beyond the retire epoch.

Tradeoffs:
- Often faster in the steady state than hazard pointers
- Simpler fast path
- Harder shutdown/thread-registration story
- Memory can grow until lagging threads advance

Good fit:
- High-throughput data structures with short critical sections
- Systems that can enforce thread registration and quiescent progress

### Practical stance

- Do not hand-roll hazard pointers or epochs unless the team already understands the operational model.
- If the task is application code, strongly consider a library container or a mutex-backed design instead.
- A lock-free algorithm without a reclamation story is incomplete.

---

## 5. MPMC Queue Boundaries

MPMC queues are where many teams overreach. The core algorithm is only part of the problem.

### Questions to force early

1. Is the queue bounded or unbounded?
2. What is the shutdown contract for blocked producers/consumers?
3. Is allocation on the hot path acceptable?
4. How is backpressure signaled?
5. What prevents false sharing on head/tail/slot metadata?
6. What reclamation strategy protects dequeued nodes or recycled slots?

### Common failure modes

- Producers spin forever after shutdown because the queue has no closed state
- Consumers read slot data before the publish flag/index is visible
- Head/tail atomics live on the same cache line and collapse under contention
- Fairness/starvation problems masked by microbenchmarks
- Benchmark looks fast, but memory usage grows without bound due to delayed reclamation

### Review stance

- Prefer bounded queues unless unbounded growth is a real requirement.
- Pad hot atomics/slots to reduce false sharing where profiling shows contention.
- Treat shutdown semantics as part of the API, not an afterthought.
- Require stress tests that cover producer/consumer exit races, full/empty transitions, and destruction during load.

If the task is "build a queue", first challenge whether a mutex + condition_variable queue already meets the SLA.

---

## 6. Review Heuristics

When reviewing advanced concurrency code:

- Find the linearization point for each operation. If you cannot identify it, the algorithm is not yet understandable enough to trust.
- Separate atomicity, ordering, and reclamation. Passing one does not imply the others.
- Ask what happens during shutdown, thread cancellation, and destructor paths.
- Ask which architectures were considered. "Works on x86" is not evidence.
- Prefer deleting a custom lock-free structure over debugging it forever if product constraints do not require it.
