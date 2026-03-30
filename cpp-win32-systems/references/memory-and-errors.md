# Memory & Error Handling Patterns

## Table of Contents
1. HANDLE RAII Patterns
2. Virtual Memory
3. SEH & Crashdump
4. String Encoding (ANSI ↔ Unicode)
5. Error Handling
6. Console API
7. Debugging Helpers
8. Environment Variables

## 1. HANDLE RAII Patterns

### Generic HANDLE wrapper

```cpp
struct HandleDeleter {
    using pointer = HANDLE;
    void operator()(HANDLE h) const {
        if (h && h != INVALID_HANDLE_VALUE) CloseHandle(h);
    }
};
using UniqueHandle = std::unique_ptr<void, HandleDeleter>;

// Usage
UniqueHandle file(CreateFileW(path, GENERIC_READ, 0, NULL,
    OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL));
if (file.get() == INVALID_HANDLE_VALUE) { /* error */ }
```

### Specialized deleters

```cpp
// HMODULE
struct ModuleDeleter {
    using pointer = HMODULE;
    void operator()(HMODULE h) const { if (h) FreeLibrary(h); }
};
using UniqueModule = std::unique_ptr<HMODULE, ModuleDeleter>;

// HKEY (registry)
struct RegKeyDeleter {
    using pointer = HKEY;
    void operator()(HKEY h) const { if (h) RegCloseKey(h); }
};

// GDI objects
struct GdiDeleter {
    using pointer = HGDIOBJ;
    void operator()(HGDIOBJ h) const { if (h) DeleteObject(h); }
};

// HDC
struct DcDeleter {
    using pointer = HDC;
    void operator()(HDC h) const { if (h) DeleteDC(h); }
};
```

### Scope guard (for anything)

```cpp
class ScopeGuard {
    std::function<void()> fn_;
public:
    ScopeGuard(std::function<void()> fn) : fn_(std::move(fn)) {}
    ~ScopeGuard() { if (fn_) fn_(); }
    void dismiss() { fn_ = nullptr; }

    ScopeGuard(const ScopeGuard&) = delete;
    ScopeGuard& operator=(const ScopeGuard&) = delete;
};

// Usage
void* ptr = MapViewOfFile(hMap, FILE_MAP_ALL_ACCESS, 0, 0, 0);
ScopeGuard unmap([ptr] { UnmapViewOfFile(ptr); });
```

## 2. Virtual Memory

### Reserve, commit, free

```cpp
// Reserve address space (no physical memory)
void* base = VirtualAlloc(NULL, 1 << 20, MEM_RESERVE, PAGE_NOACCESS);

// Commit pages as needed (allocates physical memory)
VirtualAlloc(base, 4096, MEM_COMMIT, PAGE_READWRITE);

// Free entire reservation
VirtualFree(base, 0, MEM_RELEASE);
```

### Change protection

```cpp
DWORD oldProtect;
VirtualProtect(addr, size, PAGE_EXECUTE_READ, &oldProtect);
// Restore later:
VirtualProtect(addr, size, oldProtect, &oldProtect);
```

### Common page protection flags

| Flag | Description |
|------|-------------|
| `PAGE_NOACCESS` | No access (guard) |
| `PAGE_READONLY` | Read only |
| `PAGE_READWRITE` | Read and write |
| `PAGE_EXECUTE_READ` | Execute and read (code) |
| `PAGE_EXECUTE_READWRITE` | Execute, read, write (JIT) |
| `PAGE_GUARD` | One-shot access trap |

### Query memory region

```cpp
MEMORY_BASIC_INFORMATION mbi;
VirtualQuery(addr, &mbi, sizeof(mbi));
// mbi.BaseAddress — region start
// mbi.RegionSize  — region size
// mbi.State       — MEM_COMMIT / MEM_RESERVE / MEM_FREE
// mbi.Protect     — current protection
// mbi.Type        — MEM_PRIVATE / MEM_MAPPED / MEM_IMAGE
```

## 3. SEH & Crashdump

### Structured Exception Handling

```cpp
// __try / __except — catch hardware exceptions
__try {
    int* p = nullptr;
    *p = 42; // Access violation
} __except (EXCEPTION_EXECUTE_HANDLER) {
    // Handle crash gracefully
}

// Filter function for selective handling
DWORD filter(DWORD code) {
    if (code == EXCEPTION_ACCESS_VIOLATION)
        return EXCEPTION_EXECUTE_HANDLER;
    return EXCEPTION_CONTINUE_SEARCH; // Let other handlers try
}

__try { dangerous(); }
__except (filter(GetExceptionCode())) { /* handled */ }
```

### MiniDump on crash

```cpp
#include <DbgHelp.h>
#pragma comment(lib, "DbgHelp.lib")

void save_dump(EXCEPTION_POINTERS* info, const wchar_t* path) {
    HANDLE hFile = CreateFileW(path, GENERIC_WRITE, 0, NULL,
        CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hFile == INVALID_HANDLE_VALUE) return;

    MINIDUMP_EXCEPTION_INFORMATION ei = {
        GetCurrentThreadId(), info, TRUE
    };
    MiniDumpWriteDump(GetCurrentProcess(), GetCurrentProcessId(), hFile,
        (MINIDUMP_TYPE)(MiniDumpNormal | MiniDumpWithHandleData |
                        MiniDumpWithProcessThreadData),
        &ei, NULL, NULL);
    CloseHandle(hFile);
}
```

### Unhandled exception filter (global crash handler)

```cpp
LONG WINAPI crash_handler(EXCEPTION_POINTERS* info) {
    save_dump(info, L"crash.dmp");
    return EXCEPTION_EXECUTE_HANDLER;
}

// Install at startup
SetUnhandledExceptionFilter(crash_handler);
```

### Vectored Exception Handler (first chance)

```cpp
LONG WINAPI vectored_handler(EXCEPTION_POINTERS* info) {
    if (info->ExceptionRecord->ExceptionCode == EXCEPTION_ACCESS_VIOLATION) {
        // Log or fix up
        return EXCEPTION_CONTINUE_EXECUTION; // Retry instruction
    }
    return EXCEPTION_CONTINUE_SEARCH; // Pass to next handler
}

PVOID handler = AddVectoredExceptionHandler(1, vectored_handler);
// 1 = first in chain

// Remove
RemoveVectoredExceptionHandler(handler);
```

## 4. String Encoding (ANSI ↔ Unicode)

### UTF-8 ↔ UTF-16 conversion

```cpp
// UTF-8 → UTF-16 (wstring)
std::wstring utf8_to_wide(const std::string& utf8) {
    if (utf8.empty()) return {};
    int len = MultiByteToWideChar(CP_UTF8, 0,
        utf8.c_str(), (int)utf8.size(), NULL, 0);
    std::wstring wide(len, 0);
    MultiByteToWideChar(CP_UTF8, 0,
        utf8.c_str(), (int)utf8.size(), wide.data(), len);
    return wide;
}

// UTF-16 → UTF-8 (string)
std::string wide_to_utf8(const std::wstring& wide) {
    if (wide.empty()) return {};
    int len = WideCharToMultiByte(CP_UTF8, 0,
        wide.c_str(), (int)wide.size(), NULL, 0, NULL, NULL);
    std::string utf8(len, 0);
    WideCharToMultiByte(CP_UTF8, 0,
        wide.c_str(), (int)wide.size(), utf8.data(), len, NULL, NULL);
    return utf8;
}
```

### Best practices

- Always use `W`-suffix Win32 APIs (`CreateFileW`, not `CreateFileA`)
- Store strings internally as `std::wstring` (UTF-16)
- Convert to UTF-8 only for file I/O, networking, or interop
- Never use `TCHAR` / `_T()` macros in new code — always Unicode

### ANSI code page conversion

```cpp
// ANSI (system code page) → UTF-16
std::wstring ansi_to_wide(const std::string& ansi) {
    int len = MultiByteToWideChar(CP_ACP, 0,
        ansi.c_str(), (int)ansi.size(), NULL, 0);
    std::wstring wide(len, 0);
    MultiByteToWideChar(CP_ACP, 0,
        ansi.c_str(), (int)ansi.size(), wide.data(), len);
    return wide;
}
```

## 5. Error Handling

### GetLastError formatted message

```cpp
std::wstring get_error_msg(DWORD err = GetLastError()) {
    if (err == 0) return {};
    LPWSTR buf = nullptr;
    FormatMessageW(
        FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM |
        FORMAT_MESSAGE_IGNORE_INSERTS,
        NULL, err, MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
        (LPWSTR)&buf, 0, NULL);
    std::wstring msg(buf ? buf : L"Unknown error");
    LocalFree(buf);
    return msg;
}
```

### HRESULT helpers

```cpp
#include <comdef.h>

std::string hresult_msg(HRESULT hr) {
    _com_error err(hr);
    return std::string(err.ErrorMessage());
}

inline void throw_if_failed(HRESULT hr, const char* ctx = "") {
    if (FAILED(hr))
        throw std::runtime_error(std::string(ctx) + ": " + hresult_msg(hr));
}
```

## 6. Console API

### Allocate console for GUI app

```cpp
AllocConsole();
FILE* fp;
freopen_s(&fp, "CONOUT$", "w", stdout);
freopen_s(&fp, "CONOUT$", "w", stderr);
freopen_s(&fp, "CONIN$", "r", stdin);
```

### Ctrl+C handler

```cpp
BOOL WINAPI console_handler(DWORD ctrl) {
    switch (ctrl) {
    case CTRL_C_EVENT:
    case CTRL_BREAK_EVENT:
    case CTRL_CLOSE_EVENT:
        g_running = false;
        return TRUE; // Handled
    }
    return FALSE;
}
SetConsoleCtrlHandler(console_handler, TRUE);
```

### Console colors

```cpp
HANDLE hCon = GetStdHandle(STD_OUTPUT_HANDLE);
SetConsoleTextAttribute(hCon, FOREGROUND_RED | FOREGROUND_INTENSITY);
printf("Error!\n");
SetConsoleTextAttribute(hCon, FOREGROUND_RED | FOREGROUND_GREEN | FOREGROUND_BLUE);
```

## 7. Debugging Helpers

```cpp
// Output to debugger (visible in VS Output window / DbgView)
OutputDebugStringW(L"Debug message\n");

// Check if debugger attached
if (IsDebuggerPresent()) {
    DebugBreak(); // Trigger breakpoint
}

// Performance measurement
LARGE_INTEGER freq, start, end;
QueryPerformanceFrequency(&freq);
QueryPerformanceCounter(&start);
do_work();
QueryPerformanceCounter(&end);
double ms = (end.QuadPart - start.QuadPart) * 1000.0 / freq.QuadPart;
```

## 8. Environment Variables

```cpp
// Read
WCHAR buf[32768];
DWORD len = GetEnvironmentVariableW(L"PATH", buf, _countof(buf));
std::wstring path(buf, len);

// Set (current process only)
SetEnvironmentVariableW(L"MY_VAR", L"value");

// Delete
SetEnvironmentVariableW(L"MY_VAR", NULL);

// Expand (resolve %VAR% references)
WCHAR expanded[MAX_PATH];
ExpandEnvironmentStringsW(L"%USERPROFILE%\\Documents", expanded, MAX_PATH);
```
