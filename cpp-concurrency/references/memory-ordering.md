# Memory Ordering

## Table of Contents
1. Ordering Levels — When to Use Each
2. Common Patterns
3. Pitfalls
4. Platform-Specific Notes

---

## 1. Ordering Levels — When to Use Each

| Ordering | Use For | Pairs With |
|----------|---------|------------|
| `relaxed` | Counters, progress indicators — only need atomicity, not synchronization | Nothing |
| `acquire` (loads) | Consumer side — see all writes before matching release store | `release` |
| `release` (stores) | Producer side — publish data so acquire load sees it | `acquire` |
| `acq_rel` (read-modify-write) | Both sides in one op (e.g., CAS in a lock) | Self |
| `seq_cst` (default) | Need global ordering across multiple atomics. Safe default when unsure | Self |

**Rule of thumb:** Start with `seq_cst`. Relax to `acquire`/`release` when you can identify the producer-consumer pair. Use `relaxed` only for independent counters/flags.

---

## 2. Common Patterns

### SPSC Queue (Ring Buffer)

```cpp
// Producer (single writer thread)
void write(const void* data, uint32_t len) {
    uint32_t w = write_idx.load(memory_order_relaxed);   // Own index: relaxed
    uint32_t r = read_idx.load(memory_order_acquire);    // Other's: acquire

    // ... copy data to buffer ...

    write_idx.store(new_w, memory_order_release);        // Publish: release
}

// Consumer (single reader thread)
bool read() {
    uint32_t r = read_idx.load(memory_order_relaxed);    // Own index: relaxed
    uint32_t w = write_idx.load(memory_order_acquire);   // Other's: acquire

    if (r == w) return false;
    // ... read data from buffer (guaranteed visible) ...

    read_idx.store(new_r, memory_order_release);         // Publish: release
}
```

**Why relaxed for own index?** Only one thread writes each index, so no synchronization needed for the thread's own reads. The acquire on the OTHER thread's index ensures we see all data written before that index was updated.

### Double-Checked Locking

```cpp
std::atomic<Singleton*> instance{nullptr};
std::mutex mtx;

Singleton* get_instance() {
    auto* p = instance.load(memory_order_acquire);
    if (!p) {
        std::lock_guard lock(mtx);
        p = instance.load(memory_order_relaxed); // Inside lock, relaxed OK
        if (!p) {
            p = new Singleton();
            instance.store(p, memory_order_release);
        }
    }
    return p;
}
```

### Reference Counting

```cpp
class RefCounted {
    std::atomic<int> ref_count_{1};
public:
    void add_ref() {
        ref_count_.fetch_add(1, memory_order_relaxed);
        // Relaxed: no data to synchronize on increment
    }
    void release() {
        if (ref_count_.fetch_sub(1, memory_order_acq_rel) == 1) {
            // acq_rel: acquire ensures we see all writes from other threads
            //          release ensures our writes are visible before delete
            delete this;
        }
    }
};
```

---

## 3. Pitfalls

### Relaxed where acquire/release is needed

```cpp
// BUG: relaxed doesn't synchronize buffer contents
buffer[0] = 42;
ready.store(true, memory_order_relaxed); // WRONG!
// Consumer may not see buffer[0] = 42 even after seeing ready == true
```

### Atomics only protect themselves

```cpp
std::atomic<bool> flag{false};
int data = 0; // NOT atomic

// Thread A
data = 42;
flag.store(true, memory_order_release);

// Thread B — data is visible ONLY because of the acquire/release pair
if (flag.load(memory_order_acquire)) {
    assert(data == 42); // Safe — but remove the ordering and it's a data race
}
```

### Lock-free ≠ wait-free

- **Lock-free**: At least one thread makes progress (no deadlocks)
- **Wait-free**: ALL threads make progress in bounded steps
- Most "lock-free" structures are NOT wait-free

---

## 4. Platform-Specific Notes

### x86/x64 (Intel/AMD)

Strong memory model (Total Store Order): loads are effectively acquire, stores are effectively release. `relaxed` often "works" on x86 even with wrong ordering. **Do NOT rely on this** — code with incorrect ordering WILL break on ARM.

### ARM / Apple Silicon

Weak memory model — all reorderings are possible. This is where incorrect ordering manifests as real bugs.

### MSVC Volatile

MSVC with `/volatile:ms` (default) makes `volatile` loads acquire and `volatile` stores release. This is non-standard — use `std::atomic` instead.
