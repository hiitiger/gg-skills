# Threads & Async

## Table of Contents
1. std::thread Pitfalls
2. std::jthread — Stop Token Patterns
3. std::async — Known Limitations
4. Future Patterns (shared_future, packaged_task)
5. Thread Lifetime Management
6. Passing Data to Threads

---

## 1. std::thread Pitfalls

- Destructor of joinable `std::thread` calls `std::terminate()` — always join or detach
- Arguments are **copied** into the thread — use `std::ref()` for references (but be careful about lifetime)
- `detach()` is almost always wrong — the thread must NOT access any stack/local data after detach
- **Prefer `std::jthread`** (C++20) to avoid the join/detach burden

---

## 2. std::jthread — Stop Token Patterns

### stop_callback — react to cancellation in blocking code

```cpp
void worker(std::stop_token stoken) {
    std::stop_callback cb(stoken, [] {
        cancel_io();  // Called when someone requests stop
    });
    while (!stoken.stop_requested()) {
        blocking_io();
    }
}
```

### jthread vs thread

| Feature | `std::thread` | `std::jthread` |
|---------|:---:|:---:|
| Auto-join on destruction | ❌ (terminates!) | ✅ |
| Cooperative cancellation | Manual | `stop_token` built-in |
| C++ standard | C++11 | C++20 |
| Recommendation | Legacy code only | **Default choice** |

---

## 3. std::async — Known Limitations

```cpp
// Pitfall 1: Blocking destructor
std::async(std::launch::async, slow_work);  // BLOCKS HERE — unnamed future

// Pitfall 2: Default policy may be deferred (never runs on another thread)
auto f = std::async(expensive_computation);  // Might not run until .get()!

// Pitfall 3: No thread reuse — spawns a new thread per call
for (int i = 0; i < 10000; ++i)
    futures.push_back(std::async(std::launch::async, work, i));  // 10000 threads!
```

| Use async when | Use something else when |
|----------------|------------------------|
| Quick one-off parallel computation | High-frequency submission → thread pool |
| Small number of parallel tasks | Fire-and-forget → jthread |
| Need result back via future | Need cancellation → jthread + stop_token |

---

## 4. Future Patterns

### std::shared_future — multiple consumers wait on one result

```cpp
std::promise<Config> promise;
std::shared_future<Config> config = promise.get_future().share();

// Multiple threads can wait on the same result
for (int i = 0; i < num_workers; ++i) {
    workers.emplace_back([config] {
        const Config& cfg = config.get();  // All get the same value
        do_work(cfg);
    });
}
promise.set_value(load_config());
```

### std::packaged_task — wrap callable, get future, run later

```cpp
std::packaged_task<int(int, int)> task(compute);
auto future = task.get_future();
std::jthread t(std::move(task), arg1, arg2);
int result = future.get();
```

---

## 5. Thread Lifetime Management

### Pattern: Worker with clean shutdown

```cpp
class Worker {
    std::jthread thread_;

public:
    void start() {
        thread_ = std::jthread([this](std::stop_token stoken) {
            run(stoken);
        });
    }

private:
    void run(std::stop_token stoken) {
        while (!stoken.stop_requested()) {
            if (auto task = try_get_task(stoken)) {
                task->execute();
            }
        }
    }
};
```

### Thread must not outlive its data

```cpp
// ❌ Dangling reference: thread outlives local data
void bad() {
    std::vector<int> data = {1, 2, 3};
    std::thread t([&data] { process(data); });
    t.detach();  // data destroyed, thread still running!
}

// ✅ Move data into thread
void good() {
    auto data = std::vector<int>{1, 2, 3};
    std::jthread t([data = std::move(data)] { process(data); });
}
```

---

## 6. Passing Data to Threads

| Method | When | Example |
|--------|------|---------|
| Copy into lambda | Small data, independent | `[data]() { ... }` |
| Move into lambda | Large data, transfer ownership | `[d = std::move(data)]() { ... }` |
| `std::ref` | Thread needs to write back to caller | `std::thread(fn, std::ref(out))` |
| shared_ptr | Data shared across multiple threads | `[sp = shared]() { sp->read(); }` |
| Channel (future/promise) | One-shot result delivery | See §4 |
| Queue | Continuous data stream | See patterns-and-architecture.md |
