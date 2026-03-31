# Patterns & Architecture

## Table of Contents
1. Producer-Consumer Queue
2. Thread Pool
3. Active Object Pattern
4. Notification + Lock-Free Data Separation

---

## 1. Producer-Consumer Queue

The fundamental concurrent pattern — decouples producers from consumers.

### Bounded blocking queue

```cpp
#include <queue>
#include <mutex>
#include <condition_variable>
#include <optional>

template <typename T>
class BlockingQueue {
    std::queue<T> queue_;
    mutable std::mutex mtx_;
    std::condition_variable not_empty_;
    std::condition_variable not_full_;
    size_t max_size_;
    bool closed_ = false;

public:
    explicit BlockingQueue(size_t max_size = 1024) : max_size_(max_size) {}

    // Producer: blocks if full
    bool push(T item) {
        std::unique_lock lock(mtx_);
        not_full_.wait(lock, [&] { return queue_.size() < max_size_ || closed_; });
        if (closed_) return false;
        queue_.push(std::move(item));
        lock.unlock();
        not_empty_.notify_one();
        return true;
    }

    // Consumer: blocks if empty, returns nullopt if closed
    std::optional<T> pop() {
        std::unique_lock lock(mtx_);
        not_empty_.wait(lock, [&] { return !queue_.empty() || closed_; });
        if (queue_.empty()) return std::nullopt;  // Closed and drained
        T item = std::move(queue_.front());
        queue_.pop();
        lock.unlock();
        not_full_.notify_one();
        return item;
    }

    // Signal shutdown: unblocks all waiters, no more pushes
    void close() {
        {
            std::lock_guard lock(mtx_);
            closed_ = true;
        }
        not_empty_.notify_all();
        not_full_.notify_all();
    }
};

// Usage
BlockingQueue<Task> work_queue(100);

// Producers
work_queue.push(Task{...});

// Consumers
while (auto task = work_queue.pop()) {
    task->execute();
}
// pop() returns nullopt after close() + drain

// Shutdown
work_queue.close();
```

### Lock-free SPSC queue (single producer, single consumer)

For hot paths where one thread produces and one consumes. See [memory-ordering.md](memory-ordering.md) for the acquire/release pattern.

```cpp
template <typename T, size_t Capacity>
class SpscQueue {
    static_assert((Capacity & (Capacity - 1)) == 0, "Capacity must be power of 2");

    std::array<T, Capacity> buffer_;
    alignas(64) std::atomic<size_t> head_{0};  // Written by consumer
    alignas(64) std::atomic<size_t> tail_{0};  // Written by producer

    static constexpr size_t mask = Capacity - 1;

public:
    bool try_push(const T& item) {
        size_t tail = tail_.load(std::memory_order_relaxed);
        size_t head = head_.load(std::memory_order_acquire);
        if (tail - head >= Capacity) return false;  // Full
        buffer_[tail & mask] = item;
        tail_.store(tail + 1, std::memory_order_release);
        return true;
    }

    bool try_pop(T& item) {
        size_t head = head_.load(std::memory_order_relaxed);
        size_t tail = tail_.load(std::memory_order_acquire);
        if (head == tail) return false;  // Empty
        item = buffer_[head & mask];
        head_.store(head + 1, std::memory_order_release);
        return true;
    }
};
```

**Key:** `alignas(64)` separates head/tail to different cache lines → prevents false sharing.

---

## 2. Thread Pool

Reuse a fixed number of threads for many tasks. Avoids the cost of creating/destroying threads.

```cpp
#include <vector>
#include <thread>
#include <queue>
#include <mutex>
#include <condition_variable>
#include <functional>
#include <future>

class ThreadPool {
    std::vector<std::jthread> workers_;
    std::queue<std::function<void()>> tasks_;
    std::mutex mtx_;
    std::condition_variable cv_;
    bool stop_ = false;

public:
    explicit ThreadPool(size_t num_threads = std::thread::hardware_concurrency()) {
        for (size_t i = 0; i < num_threads; ++i) {
            workers_.emplace_back([this] {
                while (true) {
                    std::function<void()> task;
                    {
                        std::unique_lock lock(mtx_);
                        cv_.wait(lock, [&] { return stop_ || !tasks_.empty(); });
                        if (stop_ && tasks_.empty()) return;
                        task = std::move(tasks_.front());
                        tasks_.pop();
                    }
                    task();
                }
            });
        }
    }

    // Submit a task, get a future for the result
    template <typename F, typename... Args>
    auto submit(F&& f, Args&&... args) -> std::future<std::invoke_result_t<F, Args...>> {
        using R = std::invoke_result_t<F, Args...>;
        auto task = std::make_shared<std::packaged_task<R()>>(
            [f = std::forward<F>(f), ...args = std::forward<Args>(args)]() mutable {
                return f(std::move(args)...);
            }
        );
        auto future = task->get_future();
        {
            std::lock_guard lock(mtx_);
            tasks_.push([task] { (*task)(); });
        }
        cv_.notify_one();
        return future;
    }

    ~ThreadPool() {
        {
            std::lock_guard lock(mtx_);
            stop_ = true;
        }
        cv_.notify_all();
        // jthread destructors join automatically
    }
};

// Usage
ThreadPool pool(4);
auto f1 = pool.submit(compute, arg1);
auto f2 = pool.submit(compute, arg2);
auto result = f1.get() + f2.get();
```

### Sizing guidelines

| Workload | Thread Count |
|----------|-------------|
| CPU-bound | `std::thread::hardware_concurrency()` |
| I/O-bound | 2× to 4× hardware_concurrency |
| Mixed | Profile and tune |

---

## 3. Active Object Pattern

Encapsulate a thread + message queue behind a normal method interface.

```cpp
class ActiveObject {
    BlockingQueue<std::function<void()>> queue_;
    std::jthread thread_;

public:
    ActiveObject() : thread_([this] {
        while (auto task = queue_.pop()) {  // nullopt on close + drain → exit
            (*task)();
        }
    }) {}

    // Methods look synchronous but execute on the internal thread
    std::future<int> compute(int x) {
        auto promise = std::make_shared<std::promise<int>>();
        auto future = promise->get_future();
        queue_.push([promise, x] {
            promise->set_value(x * x);
        });
        return future;
    }

    ~ActiveObject() {
        queue_.close();  // Unblocks pop() → thread exits loop → jthread joins
    }
};

// Usage — all compute() calls serialized on internal thread
ActiveObject obj;
auto f1 = obj.compute(10);
auto f2 = obj.compute(20);
// Results come back via futures
```

---

## 4. Notification + Lock-Free Data Separation

Decouple "there's work to do" (notification) from "here's the work" (data). The notification mechanism (event, semaphore, cv) wakes the consumer; the data lives in a lock-free buffer.

```
Producer                          Consumer
────────                          ────────
1. Write data to ring buffer      3. Wake from event/cv
2. Signal event (SetEvent / cv)   4. Drain ring buffer (lock-free)
```

This beats a mutex+queue when:
- Data throughput is high (lock-free path for the hot data)
- Multiple items can batch between notifications (consumer drains all available)
- Notification can be kernel-level (Win32 event, eventfd) for cross-process use

```cpp
// Lightweight example: cv for notification, SPSC queue for data
class NotifyQueue {
    SpscQueue<Task, 1024> queue_;  // Lock-free ring (see §1)
    std::mutex mtx_;
    std::condition_variable cv_;
    bool stopped_ = false;

public:
    void push(Task t) {
        while (!queue_.try_push(t)) {
            std::this_thread::yield();  // Back-pressure
        }
        cv_.notify_one();  // Just a wake-up signal, data already in ring
    }

    bool pop(Task& out) {
        // Fast path: drain without locking
        if (queue_.try_pop(out)) return true;
        // Slow path: wait for notification
        std::unique_lock lock(mtx_);
        cv_.wait(lock, [&] { return queue_.try_pop(out) || stopped_; });
        return !stopped_;
    }

    void stop() {
        { std::lock_guard lock(mtx_); stopped_ = true; }
        cv_.notify_all();
    }
};
```

On Windows, replace cv with `HANDLE` event + `WaitForSingleObject` for cross-process or kernel-level wake.
