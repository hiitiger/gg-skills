# Thread Safety Patterns

## Table of Contents
1. Cancellation — Tricky Cases
2. UI Thread / Worker Thread Boundary
3. Callback Lifetime Across Threads

---

## 1. Cancellation — Tricky Cases

Basic stop_token / atomic flag cancellation is straightforward. These patterns handle the hard cases:

### Interrupt a blocking wait

```cpp
void worker(std::stop_token stoken) {
    std::unique_lock lock(mtx_);

    // ❌ Doesn't wake when stop is requested
    cv_.wait(lock, [&] { return !queue_.empty(); });

    // ✅ Include stop check in predicate
    cv_.wait(lock, [&] { return !queue_.empty() || stoken.stop_requested(); });
    if (stoken.stop_requested()) return;

    // ✅ Or use condition_variable_any with stop_token (C++20)
    std::condition_variable_any cv;
    cv.wait(lock, stoken, [&] { return !queue_.empty(); });
}
```

### Win32 multi-event wait — "work OR quit"

On Windows, `WaitForMultipleObjects` is the idiomatic way to make a blocking thread respond to multiple signals (new work, shutdown, timeout) without polling.

```cpp
void worker(HANDLE ready_event, HANDLE quit_event) {
    HANDLE events[] = {quit_event, ready_event};
    while (true) {
        DWORD ret = WaitForMultipleObjects(2, events, FALSE, INFINITE);
        if (ret == WAIT_OBJECT_0)       // quit_event signaled
            return;
        if (ret == WAIT_OBJECT_0 + 1) { // ready_event signaled
            process_work();
        }
    }
}
// Shutdown: SetEvent(quit_event) — thread wakes and exits cleanly
```

Put the quit event first so `WAIT_OBJECT_0` is always the exit path. Use manual-reset for quit (all waiters wake) and auto-reset for work (one waiter per signal).

### Cancel blocking I/O

Blocking I/O can't be interrupted by stop_token alone — use platform-specific cancellation via stop_callback:

```cpp
// Windows: CancelIoEx
void worker(std::stop_token stoken, HANDLE file) {
    std::stop_callback cb(stoken, [file] {
        CancelIoEx(file, nullptr);  // Interrupts pending I/O
    });
    ReadFile(file, buf, size, &read, nullptr);  // Returns ERROR_OPERATION_ABORTED
}

// POSIX: self-pipe trick or eventfd
// Signal the blocked thread by writing to a pipe/eventfd it's polling
```

---

## 2. UI Thread / Worker Thread Boundary

### Pattern: Post result back to UI thread

```cpp
// Windows — PostMessage
void background_work(HWND hwnd) {
    std::jthread t([hwnd] {
        auto result = expensive_computation();
        PostMessage(hwnd, WM_APP_RESULT, 0, reinterpret_cast<LPARAM>(
            new Result(std::move(result))
        ));
    });
}

case WM_APP_RESULT: {
    auto* result = reinterpret_cast<Result*>(lParam);
    update_ui(*result);  // Safe: on UI thread
    delete result;
    return 0;
}
```

### Pattern: Generic UI dispatcher

```cpp
class UiDispatcher {
    BlockingQueue<std::function<void()>> queue_;

public:
    void post(std::function<void()> fn) {
        queue_.push(std::move(fn));
        // Wake UI thread (PostMessage, CFRunLoopSourceSignal, etc.)
    }

    void drain() {  // Called from UI thread's message loop
        while (auto fn = queue_.pop_nowait()) {
            (*fn)();
        }
    }
};
```

### Pattern: Shared state with polling (read from UI, write from worker)

```cpp
class SharedModel {
    mutable std::shared_mutex mtx_;
    ProgressInfo progress_;

public:
    void update_progress(float percent, const std::string& status) {
        std::unique_lock lock(mtx_);
        progress_ = {percent, status};
    }

    ProgressInfo get_progress() const {
        std::shared_lock lock(mtx_);
        return progress_;
    }
};
```

### Anti-patterns

```cpp
// ❌ Worker thread directly touches UI
std::jthread t([label] {
    label->set_text(compute());  // CRASH: UI access from worker thread
});

// ❌ UI thread blocks on worker result
void on_button_click() {
    auto result = std::async(std::launch::async, expensive_work).get();  // UI freezes
}
```

---

## 3. Callback Lifetime Across Threads

### Solution 1: shared_from_this

```cpp
class Processor : public std::enable_shared_from_this<Processor> {
    std::vector<int> data_;

public:
    void start() {
        auto self = shared_from_this();
        std::jthread t([self] {
            self->process(self->data_);  // Safe: shared_ptr keeps alive
        });
    }
};
// MUST be created as: auto p = std::make_shared<Processor>();
```

### Solution 2: weak_ptr for periodic work

```cpp
class Processor : public std::enable_shared_from_this<Processor> {
public:
    void start_periodic() {
        std::weak_ptr<Processor> weak = weak_from_this();
        std::jthread t([weak] {
            while (auto self = weak.lock()) {
                self->do_work();
                std::this_thread::sleep_for(1s);
            }
            // Object destroyed → weak.lock() returns nullptr → thread exits
        });
    }
};
```

### Solution 3: Own the thread — declaration order matters!

```cpp
// ⚠️ Member destruction order is reverse of declaration order.
// thread_ must be declared AFTER data_ so it joins first.

class Processor {
    std::vector<int> data_;    // 1. Destroyed second (after thread joins)
    std::jthread thread_;      // 2. Destroyed first (joins → data_ still alive)

    void start() {
        thread_ = std::jthread([this](std::stop_token st) {
            while (!st.stop_requested()) {
                process(data_);  // Safe: jthread joins before data_ destroyed
            }
        });
    }
};
```
