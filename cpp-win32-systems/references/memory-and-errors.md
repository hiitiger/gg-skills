# Memory & Errors — Decisions & Pitfalls

## HANDLE RAII

```cpp
struct HandleDeleter {
    using pointer = HANDLE;
    void operator()(HANDLE h) const {
        if (h && h != INVALID_HANDLE_VALUE) CloseHandle(h);
    }
};
using UniqueHandle = std::unique_ptr<void, HandleDeleter>;
```

Write the same pattern for other handle types, matching the closer:

| Type | Closer | Notes |
|------|--------|-------|
| `HMODULE` | `FreeLibrary` | |
| `HKEY` | `RegCloseKey` | |
| `HGDIOBJ` | `DeleteObject` | Must deselect from DC first |
| `HDC` | `DeleteDC` | For created DCs; `ReleaseDC` for `GetDC` |
| `SOCKET` | `closesocket` | Not `CloseHandle` |
| `HANDLE` (file mapping view) | `UnmapViewOfFile` | Not `CloseHandle` |
| `FindFirstFile` handle | `FindClose` | Not `CloseHandle` |

For one-off cleanup without a dedicated deleter, use a `ScopeGuard` (lambda in destructor, `.dismiss()` to cancel).

## Virtual Memory

Reserve-then-commit: `VirtualAlloc(MEM_RESERVE)` claims address space without physical memory, `VirtualAlloc(MEM_COMMIT)` backs pages on demand. Used for growable buffers, custom allocators, JIT. Free entire reservation with `VirtualFree(MEM_RELEASE)`.

`VirtualProtect` changes page protection. `PAGE_GUARD` fires a one-shot exception on first access — useful for stack probing or lazy initialization.

## SEH & Crashdump

- `__try/__except` catches hardware exceptions (access violation, div-by-zero, stack overflow) that C++ `try/catch` cannot.
- Don't mix `__try/__except` and C++ exceptions in the same function — MSVC forbids it.
- Filter with `GetExceptionCode()` — return `EXCEPTION_EXECUTE_HANDLER` to handle, `EXCEPTION_CONTINUE_SEARCH` to pass.
- `SetUnhandledExceptionFilter` installs a global crash handler — call `MiniDumpWriteDump` there to create a `.dmp` file.
- Vectored exception handlers (`AddVectoredExceptionHandler`) fire before SEH frames — useful for global logging. Returning `EXCEPTION_CONTINUE_EXECUTION` retries the faulting instruction (infinite loop if cause isn't fixed).

## String Encoding

- Store strings as `std::wstring` (UTF-16) internally.
- Always use W-suffix APIs.
- Convert with `MultiByteToWideChar(CP_UTF8, ...)` / `WideCharToMultiByte(CP_UTF8, ...)` at I/O boundaries.
- Never use `TCHAR` / `_T()` in new code.

## Error Handling Pitfalls

- `GetLastError()` is overwritten by the next Win32 call — capture immediately after failure, before any cleanup code.
- `FormatMessageW` with `FORMAT_MESSAGE_ALLOCATE_BUFFER` allocates via `LocalAlloc` — must `LocalFree` the buffer.
- For HRESULT, `_com_error(hr).ErrorMessage()` gives a readable string.
