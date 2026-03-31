# Synchronization

## Table of Contents
1. Mutex & Lock Guard Selection
2. Condition Variable Pitfalls
3. Deadlock Prevention (Advanced)
4. Atomic vs Lock Decision Guide
5. Atomic Patterns
6. Sharded Locking (Bucket-Level)
7. shared_mutex — When (and When Not)

---

## 1. Mutex & Lock Guard Selection

| Mutex | Use When |
|-------|----------|
| `std::mutex` | Default for exclusive access |
| `std::timed_mutex` | Need `try_lock_for` timeout |
| `std::recursive_mutex` | Same thread re-enters lock (**avoid — redesign instead**) |
| `std::shared_mutex` | Multiple readers, single writer (see §6 for criteria) |

| Guard | Use When |
|-------|----------|
| `scoped_lock` | **Default.** Single or multiple mutexes, deadlock-free |
| `lock_guard` | Single mutex, no need for unlock/relock |
| `unique_lock` | Condition variables, deferred/timed locking, manual unlock |
| `shared_lock` | Read side of `shared_mutex` |

---

## 2. Condition Variable Pitfalls

```cpp
// ❌ Missing predicate — spurious wakeups cause bugs
cv.wait(lock);  // May wake without notify!

// ✅ Always use predicate
cv.wait(lock, [&] { return !queue.empty(); });

// ❌ Using lock_guard with condition_variable
std::lock_guard lock(mtx);
cv.wait(lock, pred);  // COMPILE ERROR: cv.wait needs unique_lock
```

### Notify placement tradeoff

```cpp
// Outside lock — waiter can acquire immediately, avoids a wake-then-block cycle
// Inside lock  — simpler, and some implementations optimize this case
// Default to outside lock under contention; inside lock is fine for clarity
{
    std::lock_guard lock(mtx);
    data = new_value;
}
cv.notify_one();  // Preferred under contention
```

### Timed wait

```cpp
std::unique_lock lock(mtx);
if (cv.wait_for(lock, 5s, [&] { return ready; })) {
    // Condition met within 5 seconds
} else {
    // Timeout
}
```

---

## 3. Deadlock Prevention (Advanced)

Solutions 1–2 (consistent ordering, `scoped_lock`) are well-known. These are for when those aren't enough:

### Try-lock with backoff

```cpp
void transfer(Account& a, Account& b, int amount) {
    while (true) {
        std::unique_lock lock_a(a.mtx, std::try_to_lock);
        std::unique_lock lock_b(b.mtx, std::try_to_lock);
        if (lock_a && lock_b) {
            a.balance -= amount;
            b.balance += amount;
            return;
        }
        std::this_thread::yield();  // Back off and retry
    }
}
```

### Lock hierarchy

```cpp
// Assign levels to mutexes; only lock lower level while holding higher
// Level 3: database_mtx (lock first)
// Level 2: cache_mtx
// Level 1: stats_mtx (lock last)
// Detect violations at runtime with a thread_local tracking the current level
```

### Lock held during callback — hidden deadlock

```cpp
// ❌ Callback may lock another mutex, or call back into us
{
    std::lock_guard lock(mtx);
    callback();  // Unknown code under lock!
}

// ✅ Copy data out, release lock, then call
std::vector<Callback> cbs;
{ std::lock_guard lock(mtx); cbs = callbacks_; }
for (auto& cb : cbs) cb();
```

---

## 4. Atomic vs Lock Decision Guide

```
Is the shared state a single scalar value (int, bool, pointer)?
├─ Yes → Can you express the operation as a single atomic op (load/store/CAS)?
│  ├─ Yes → std::atomic ✅
│  └─ No (need read-modify-write on complex state) → mutex
└─ No (struct, multiple fields, invariant across fields) → mutex

Additional considerations:
├─ Contention is very high? → Consider lock-free queue or partitioned data
├─ Read-heavy, write-rare? → shared_mutex or read-copy-update
└─ Performance-critical tight loop? → Profile! atomic may still lose to batching
```

---

## 5. Atomic Patterns

### CAS loop — lock-free update

```cpp
int old_val = counter.load();
while (!counter.compare_exchange_weak(old_val, old_val + delta)) {
    // old_val updated to current value, retry
}
```

### Spinlock (short critical sections only)

```cpp
std::atomic_flag spinlock = ATOMIC_FLAG_INIT;
while (spinlock.test_and_set(std::memory_order_acquire)) {
    // Spin — consider _mm_pause() on x86 or yield
}
// Critical section
spinlock.clear(std::memory_order_release);
```

### CAS state machine — lock-free state transitions

When an object moves through discrete states (connecting → requesting → connected → disconnecting), CAS lets exactly one thread win each transition without locks.

```cpp
enum class State : int { Idle, Requesting, Connected, Error };
std::atomic<State> state{State::Idle};

// Only one thread succeeds; losers see updated `expected` and can react
State expected = State::Idle;
if (state.compare_exchange_strong(expected, State::Requesting,
        std::memory_order_acq_rel)) {
    // Won the transition — proceed with connection setup
} else {
    // expected now holds the actual state (e.g., another thread got there first)
}
```

Useful for: connection handshakes, resource lifecycle, protocol state machines. Each transition is a single CAS — no mutex, no blocking.

→ For acquire/release pairs and detailed memory ordering, see [memory-ordering.md](memory-ordering.md)

---

## 6. Sharded Locking (Bucket-Level)

When a single mutex becomes a bottleneck on a concurrent data structure, partition the data into N buckets, each with its own lock. Threads hitting different buckets don't contend.

```cpp
template <typename K, typename V, size_t N = 16>
class ShardedMap {
    struct Bucket {
        std::shared_mutex mtx;
        std::unordered_map<K, V> map;
    };
    std::array<Bucket, N> buckets_;

    Bucket& bucket_for(const K& key) {
        return buckets_[std::hash<K>{}(key) % N];
    }

public:
    V get(const K& key) {
        auto& b = bucket_for(key);
        std::shared_lock lock(b.mtx);
        auto it = b.map.find(key);
        return (it != b.map.end()) ? it->second : V{};
    }

    void set(const K& key, V value) {
        auto& b = bucket_for(key);
        std::unique_lock lock(b.mtx);
        b.map[key] = std::move(value);
    }
};
```

**When to use:** high-contention map/set with many threads. **Don't use** when contention is low — the overhead of N mutexes isn't worth it.

Consider `alignas(64)` on each bucket to prevent false sharing between adjacent locks.

---

## 7. shared_mutex — When (and When Not)

`shared_mutex` is **heavier** than `mutex`. Only use when:
- Reads vastly outnumber writes (>10:1 ratio)
- Read operations are non-trivial (otherwise mutex overhead dominates)
- Don't use for balanced read/write — plain `mutex` is faster
