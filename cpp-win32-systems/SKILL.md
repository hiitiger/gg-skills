---
name: cpp-win32-systems
description: Windows C++ systems programming with Win32 API. Use when the task is primarily about Win32 API calls — GUI windows, message loops, GDI, DLL/COM, services, registry, named pipes, shared memory, Winsock, IOCP, SEH, API hooking, or code using HWND/HANDLE/HRESULT/ComPtr/WndProc/WM_ messages.
---

# Windows C++ Systems Programming

## How to Use

1. Use the decision tree to pick **one** reference — read only that file.
2. If the task spans two domains (e.g., IOCP + DLL), read the second reference on demand.
3. If the task is primarily about std concurrency, modern C++, or .dmp analysis, hand off to the corresponding skill instead.

## References

| Category | When to Use | Reference |
|----------|------------|-----------|
| **Window & GUI** | Windows, messages, GDI, DPI | [gui-and-windows.md](references/gui-and-windows.md) |
| **Thread & Process** | Threads, thread pools, sync, child processes | [threads-and-processes.md](references/threads-and-processes.md) |
| **IPC & Networking** | Shared memory, pipes, sockets, cross-process sync | [ipc-and-networking.md](references/ipc-and-networking.md) |
| **I/O & File System** | File I/O, memory mapping, async I/O, IOCP | [io-and-filesystem.md](references/io-and-filesystem.md) |
| **System Services** | DLL, COM, services, registry, Shell, UAC | [system-and-services.md](references/system-and-services.md) |
| **Memory & Errors** | HANDLE RAII, virtual memory, SEH, encoding, errors | [memory-and-errors.md](references/memory-and-errors.md) |
| **Utilities** | Console, debug output, env vars | [utilities.md](references/utilities.md) |
| **Hooks & Inspection** | Module enumeration, Detours, VTable, message hooks | [hooks-and-inspection.md](references/hooks-and-inspection.md) |

## Decision Tree

```
├─ Desktop app with window → gui-and-windows.md
├─ Background work / parallelism → threads-and-processes.md
│  └─ std::thread / std::mutex / C++ sync? → cpp-concurrency skill
├─ Cross-process communication → ipc-and-networking.md
├─ File / disk / async I/O → io-and-filesystem.md
├─ DLL / COM / system integration → system-and-services.md
├─ Hooking / inspection → hooks-and-inspection.md
├─ Debugging / crash analysis → memory-and-errors.md § SEH
│  └─ Crash dump (.dmp) file? → windbg-crash skill
├─ Console / debug / env vars → utilities.md
└─ RAII, smart pointers, modern C++ → cpp-modern-dev skill
```

## Core Rules

1. **HANDLE RAII** — wrap every Win32 resource in a RAII type. Use `UniqueHandle` for HANDLE (see [memory-and-errors.md](references/memory-and-errors.md) for the deleter and specialized variants). General RAII concepts → `cpp-modern-dev` skill.

2. **Always W-suffix APIs** — `CreateFileW`, not `CreateFileA`. Never use `TCHAR`/`_T()` in new code.

3. **Error checking** — every Win32 call can fail. Three models:
   - `BOOL` + `GetLastError()` — most Win32. Capture immediately, it's overwritten by the next call.
   - `HRESULT` — COM/DirectX. Use `FAILED(hr)`, don't compare to `S_OK` (some success codes are nonzero).
   - `__try/__except` — hardware exceptions only. Not for flow control. Cannot mix with C++ exceptions in the same function.

4. **Win32 vs Standard C++** — prefer `std::thread`/`std::mutex`/`std::fstream` for portable code. Use Win32 when you need: IOCP, named kernel objects, security descriptors, window messages, COM, registry, or `WaitForMultipleObjects`.
