# Thread & Process — Decisions & Pitfalls

## Creating Threads — Which API?

- **`std::thread` / `std::jthread`** — prefer for portable code. See `cpp-concurrency` skill.
- **`_beginthreadex`** — use when you need a Win32 HANDLE (for `WaitForMultipleObjects`) AND the thread calls CRT functions. `CreateThread` doesn't initialize per-thread CRT state (errno, strtok, locale) — silent corruption if you use CRT.
- **`CreateThread`** — only for threads that exclusively call Win32 APIs, no CRT.

Always wrap the returned HANDLE in `UniqueHandle`.

## Synchronization — Which Primitive?

- **`CRITICAL_SECTION`** — recursive, supports spin count (good when contention is rare), intra-process only. Needs `InitializeCriticalSection`/`DeleteCriticalSection`.
- **`SRWLock`** — pointer-sized, faster under contention, supports shared/exclusive reads, non-recursive. No cleanup needed (`= SRWLOCK_INIT`).
- **`Event`** — simple signal/wait. Auto-reset wakes one waiter, manual-reset wakes all.
- **Named Mutex / Event / Semaphore** — cross-process. See ipc-and-networking.md.
- **`std::mutex` / `std::condition_variable`** — see `cpp-concurrency` skill.

`CRITICAL_SECTION` and `SRWLock` are compatible with `std::lock_guard` / `std::unique_lock` if you add `lock()`/`unlock()` methods.

## Thread Pool

Win32 thread pool (`TrySubmitThreadpoolCallback`, `CreateThreadpoolWork`, `CreateThreadpoolTimer`) manages thread lifetime and scales with CPU cores. Prefer over manually spawning threads for many short-lived tasks.

## CreateProcess Pitfalls

- **`lpCommandLine` must be writable** — `CreateProcessW` may modify it in-place. Always pass a `std::wstring::data()`, never a string literal.
- Immediately wrap `pi.hProcess` and `pi.hThread` in `UniqueHandle`.
- To capture child stdout/stderr: create a pipe with `SECURITY_ATTRIBUTES.bInheritHandle = TRUE`, set `STARTF_USESTDHANDLES`, close the parent's write end after `CreateProcess`.

## Job Objects

Kill-on-close job prevents orphaned child processes — without it, crashing the parent leaves children running. `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` terminates all assigned processes when the job handle closes.
