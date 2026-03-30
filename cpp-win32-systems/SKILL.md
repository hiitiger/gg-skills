---
name: cpp-win32-systems
description: Windows C++ systems programming with Win32 API. Use when writing C++ code for Windows desktop applications, GUI windows, message loops, threads, processes, DLL development, COM interfaces, services, shared memory, named pipes, Winsock networking, async I/O (IOCP), registry, file I/O, GDI drawing, or any Win32 API usage. Triggers on HWND, HANDLE, HINSTANCE, CreateWindow, GetMessage, DispatchMessage, CreateThread, CreateProcess, LoadLibrary, CreateFileMapping, CreateNamedPipe, WSAStartup, CreateIoCompletionPort, SetWindowLongPtr, RegisterClassEx, WndProc, LRESULT CALLBACK, WM_ messages, HRESULT, ComPtr, DllMain, VirtualAlloc, BeginPaint, or any Windows-specific C++ code.
---

# Windows C++ Systems Programming

## Categories

| Category | When to Use | Reference |
|----------|------------|-----------|
| **Window & GUI** | Creating windows, handling messages, drawing, DPI | [gui-and-windows.md](references/gui-and-windows.md) |
| **Thread & Process** | Threads, thread pools, sync, child processes | [threads-and-processes.md](references/threads-and-processes.md) |
| **IPC & Networking** | Shared memory, pipes, sockets, cross-process sync | [ipc-and-networking.md](references/ipc-and-networking.md) |
| **I/O & File System** | File read/write, memory mapping, async I/O, IOCP | [io-and-filesystem.md](references/io-and-filesystem.md) |
| **System Services** | DLL, COM, services, registry, Shell, UAC | [system-and-services.md](references/system-and-services.md) |
| **Memory & Errors** | HANDLE RAII, virtual memory, SEH, encoding, errors | [memory-and-errors.md](references/memory-and-errors.md) |

## Quick Decision Tree

```
What are you building?
├─ Desktop app with window → gui-and-windows.md
│  ├─ Need custom drawing/paint? → GDI section
│  └─ High-DPI support? → DPI section
├─ Background work / parallelism → threads-and-processes.md
│  ├─ Simple worker thread? → CreateThread
│  ├─ Many short tasks? → Thread Pool
│  └─ Launch external program? → CreateProcess
├─ Cross-process communication → ipc-and-networking.md
│  ├─ Shared data buffer? → Shared Memory
│  ├─ Stream / request-response? → Named Pipes
│  ├─ Network communication? → Winsock
│  └─ Signal / coordinate? → Named Events / Mutexes
├─ File / disk / async I/O → io-and-filesystem.md
│  ├─ Read/write files? → CreateFile
│  ├─ Map file to memory? → Memory-Mapped Files
│  ├─ High-perf async? → IOCP
│  └─ Watch for changes? → ReadDirectoryChanges
├─ DLL / COM / system integration → system-and-services.md
│  ├─ Building a DLL? → DLL Patterns
│  ├─ Using COM objects? → COM / ComPtr
│  ├─ Windows service? → Service Patterns
│  └─ Registry / Shell / elevation? → Respective sections
└─ Memory / error handling → memory-and-errors.md
   ├─ HANDLE leak prevention? → HANDLE RAII
   ├─ Crash dump? → SEH & MiniDump
   └─ ANSI ↔ Unicode? → String Encoding
```

## Essential Patterns (Always Apply)

### HANDLE RAII — wrap every HANDLE

See [references/memory-and-errors.md](references/memory-and-errors.md) § "HANDLE RAII Patterns" for full set of RAII wrappers (HANDLE, HMODULE, HKEY, GDI, HDC, ScopeGuard).

```cpp
// Core pattern used throughout all references
struct HandleDeleter {
    using pointer = HANDLE;
    void operator()(HANDLE h) const {
        if (h && h != INVALID_HANDLE_VALUE) CloseHandle(h);
    }
};
using UniqueHandle = std::unique_ptr<void, HandleDeleter>;
```

### Error checking — every Win32 call can fail

```cpp
// For BOOL-returning functions
if (!CreateProcessW(...)) {
    DWORD err = GetLastError();
    // handle error
}

// For HRESULT-returning functions (COM/DirectX)
HRESULT hr = device->CreateBuffer(&desc, &data, &buf);
if (FAILED(hr)) { /* handle */ }
```

### Unicode — always use W-suffix APIs

```cpp
// YES: Wide char APIs
CreateFileW(L"path.txt", ...);
MessageBoxW(hwnd, L"text", L"caption", MB_OK);

// NO: Don't use A-suffix (ANSI) APIs in new code
// CreateFileA("path.txt", ...);
```
