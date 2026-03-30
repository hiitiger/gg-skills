# Thread & Process Patterns

## Table of Contents
1. Creating Threads
2. Thread Synchronization
3. Thread Pool
4. Thread-Local Storage
5. Creating Processes
6. Process Enumeration
7. Job Objects

## 1. Creating Threads

### CreateThread with RAII handle

```cpp
// UniqueHandle defined in SKILL.md
UniqueHandle worker(CreateThread(NULL, 0,
    [](LPVOID param) -> DWORD {
        auto* ctx = (WorkContext*)param;
        ctx->run();
        return 0;
    }, &context, 0, nullptr));

// Wait for completion
WaitForSingleObject(worker.get(), INFINITE);

// Get exit code
DWORD exitCode;
GetExitCodeThread(worker.get(), &exitCode);
```

### _beginthreadex (preferred for CRT-safe code)

```cpp
#include <process.h>

unsigned __stdcall thread_func(void* arg) {
    // CRT is properly initialized
    printf("thread running\n");
    return 0;
}

HANDLE h = (HANDLE)_beginthreadex(NULL, 0, thread_func, &data, 0, nullptr);
UniqueHandle thread(h);  // RAII wrap
WaitForSingleObject(thread.get(), INFINITE);
```

**Rule**: Use `_beginthreadex` instead of `CreateThread` when the thread uses C runtime functions (printf, malloc, strtok, etc.).

### std::thread (C++11, simplest)

```cpp
std::thread worker([&] {
    do_work(data);
});
worker.join(); // or worker.detach()
```

## 2. Thread Synchronization

### CRITICAL_SECTION (lightweight, intra-process only)

```cpp
class CriticalSection {
    CRITICAL_SECTION cs_;
public:
    CriticalSection()  { InitializeCriticalSectionAndSpinCount(&cs_, 4000); }
    ~CriticalSection() { DeleteCriticalSection(&cs_); }
    void lock()   { EnterCriticalSection(&cs_); }
    bool try_lock() { return TryEnterCriticalSection(&cs_) != 0; }
    void unlock() { LeaveCriticalSection(&cs_); }
};

CriticalSection cs;
{
    std::lock_guard<CriticalSection> lock(cs);
    // thread-safe access
}
```

### SRWLock (slim reader/writer, Windows Vista+)

```cpp
SRWLOCK lock = SRWLOCK_INIT; // No cleanup needed

// Exclusive (write)
AcquireSRWLockExclusive(&lock);
// ... modify data ...
ReleaseSRWLockExclusive(&lock);

// Shared (read)
AcquireSRWLockShared(&lock);
// ... read data ...
ReleaseSRWLockShared(&lock);
```

### Condition Variable

```cpp
CONDITION_VARIABLE cv = CONDITION_VARIABLE_INIT;
SRWLOCK lock = SRWLOCK_INIT;
bool ready = false;

// Wait side
AcquireSRWLockExclusive(&lock);
while (!ready)
    SleepConditionVariableSRW(&cv, &lock, INFINITE, 0);
// process data
ReleaseSRWLockExclusive(&lock);

// Signal side
AcquireSRWLockExclusive(&lock);
ready = true;
ReleaseSRWLockExclusive(&lock);
WakeConditionVariable(&cv);     // One waiter
WakeAllConditionVariable(&cv);  // All waiters
```

### Event (intra-process, simpler than CV for single-signal)

```cpp
HANDLE evt = CreateEventW(NULL, FALSE, FALSE, NULL); // Auto-reset, unnamed

// Worker thread
SetEvent(evt); // Signal

// Main thread
WaitForSingleObject(evt, INFINITE); // Block until signaled
CloseHandle(evt);
```

### WaitForMultipleObjects

```cpp
HANDLE handles[] = { thread1, thread2, stopEvent };
DWORD r = WaitForMultipleObjects(3, handles, FALSE, 5000);
// FALSE = wait for ANY, TRUE = wait for ALL
// Returns WAIT_OBJECT_0 + index, WAIT_TIMEOUT, or WAIT_FAILED
```

## 3. Thread Pool

### Simple work submission

```cpp
TrySubmitThreadpoolCallback(
    [](PTP_CALLBACK_INSTANCE inst, PVOID ctx) {
        auto* task = (Task*)ctx;
        task->execute();
    }, &my_task, NULL);
```

### Work object (reusable, cancellable)

```cpp
PTP_WORK work = CreateThreadpoolWork(
    [](PTP_CALLBACK_INSTANCE, PVOID ctx, PTP_WORK) {
        do_work((WorkItem*)ctx);
    }, &item, NULL);

SubmitThreadpoolWork(work);
WaitForThreadpoolWorkCallbacks(work, FALSE); // FALSE = don't cancel pending
CloseThreadpoolWork(work);
```

### Timer (periodic task)

```cpp
PTP_TIMER timer = CreateThreadpoolTimer(
    [](PTP_CALLBACK_INSTANCE, PVOID ctx, PTP_TIMER) {
        do_periodic_check();
    }, nullptr, NULL);

// Start: due in 0ms, repeat every 1000ms
FILETIME due = {}; // 0 = immediate
SetThreadpoolTimer(timer, &due, 1000, 0);

// Stop
SetThreadpoolTimer(timer, NULL, 0, 0);
WaitForThreadpoolTimerCallbacks(timer, TRUE);
CloseThreadpoolTimer(timer);
```

### Wait object (wait for kernel object on pool thread)

```cpp
PTP_WAIT pw = CreateThreadpoolWait(
    [](PTP_CALLBACK_INSTANCE, PVOID ctx, PTP_WAIT, TP_WAIT_RESULT result) {
        if (result == WAIT_OBJECT_0) {
            // Event was signaled
        }
    }, &context, NULL);

SetThreadpoolWait(pw, hEvent, NULL); // NULL timeout = infinite
// ...
CloseThreadpoolWait(pw);
```

## 4. Thread-Local Storage

### C++11 thread_local (preferred)

```cpp
thread_local int t_error_code = 0;
thread_local std::vector<int> t_buffer;
```

### Win32 TLS (for DLLs or pre-C++11)

```cpp
static DWORD g_tls_index = TLS_OUT_OF_INDEXES;

// DLL_PROCESS_ATTACH
g_tls_index = TlsAlloc();

// Per-thread set/get
TlsSetValue(g_tls_index, (LPVOID)my_data);
auto* data = (MyData*)TlsGetValue(g_tls_index);

// DLL_PROCESS_DETACH
TlsFree(g_tls_index);
```

## 5. Creating Processes

### Launch and forget

```cpp
bool launch(const std::wstring& cmd_line) {
    STARTUPINFOW si = { sizeof(si) };
    PROCESS_INFORMATION pi = {};
    std::wstring cmd = cmd_line; // CreateProcessW may modify

    BOOL ok = CreateProcessW(NULL, cmd.data(), NULL, NULL,
        FALSE, CREATE_NEW_PROCESS_GROUP, NULL, NULL, &si, &pi);

    if (ok) {
        CloseHandle(pi.hThread);
        CloseHandle(pi.hProcess);
    }
    return ok;
}
```

### Launch, wait, get exit code

```cpp
int run_and_wait(const std::wstring& cmd) {
    STARTUPINFOW si = { sizeof(si) };
    PROCESS_INFORMATION pi = {};
    std::wstring buf = cmd;

    if (!CreateProcessW(NULL, buf.data(), NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi))
        return -1;

    CloseHandle(pi.hThread);
    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD exitCode;
    GetExitCodeProcess(pi.hProcess, &exitCode);
    CloseHandle(pi.hProcess);
    return (int)exitCode;
}
```

### Redirect child stdout/stderr

```cpp
HANDLE hReadPipe, hWritePipe;
SECURITY_ATTRIBUTES sa = { sizeof(sa), NULL, TRUE }; // Inheritable
CreatePipe(&hReadPipe, &hWritePipe, &sa, 0);
SetHandleInformation(hReadPipe, HANDLE_FLAG_INHERIT, 0); // Parent-side not inherited

STARTUPINFOW si = { sizeof(si) };
si.dwFlags = STARTF_USESTDHANDLES;
si.hStdOutput = hWritePipe;
si.hStdError  = hWritePipe;

PROCESS_INFORMATION pi = {};
CreateProcessW(NULL, cmd, NULL, NULL, TRUE, 0, NULL, NULL, &si, &pi);
CloseHandle(hWritePipe); // Close parent's write end

// Read child output
char buf[4096];
DWORD bytesRead;
while (ReadFile(hReadPipe, buf, sizeof(buf), &bytesRead, NULL) && bytesRead > 0) {
    // process output
}
CloseHandle(hReadPipe);
```

## 6. Process Enumeration

```cpp
#include <TlHelp32.h>

std::vector<DWORD> find_processes(const wchar_t* name) {
    std::vector<DWORD> pids;
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    PROCESSENTRY32W pe = { sizeof(pe) };
    if (Process32FirstW(snap, &pe)) {
        do {
            if (_wcsicmp(pe.szExeFile, name) == 0)
                pids.push_back(pe.th32ProcessID);
        } while (Process32NextW(snap, &pe));
    }
    CloseHandle(snap);
    return pids;
}
```

### Check if process is running

```cpp
bool is_alive(DWORD pid) {
    HANDLE h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pid);
    if (!h) return false;
    DWORD code;
    GetExitCodeProcess(h, &code);
    CloseHandle(h);
    return code == STILL_ACTIVE;
}
```

## 7. Job Objects

Job objects manage a group of processes as a unit: impose limits, kill all on exit.

```cpp
// Create job that kills children when handle closes
HANDLE job = CreateJobObjectW(NULL, NULL);
JOBOBJECT_EXTENDED_LIMIT_INFORMATION info = {};
info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
SetInformationJobObject(job, JobObjectExtendedLimitInformation, &info, sizeof(info));

// Assign child process to job
AssignProcessToJobObject(job, pi.hProcess);

// All processes in job are terminated when job handle is closed
CloseHandle(job);
```
