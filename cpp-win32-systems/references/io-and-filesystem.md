# I/O & File System Patterns

## Table of Contents
1. File Read/Write
2. Memory-Mapped Files
3. Async I/O (Overlapped)
4. I/O Completion Ports (IOCP)
5. Directory Watching
6. File Enumeration
7. Temporary Files

## 1. File Read/Write

### Read entire file

```cpp
std::vector<uint8_t> read_file(const wchar_t* path) {
    HANDLE hFile = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ,
        NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hFile == INVALID_HANDLE_VALUE) return {};

    LARGE_INTEGER size;
    GetFileSizeEx(hFile, &size);

    std::vector<uint8_t> data(size.QuadPart);
    DWORD bytesRead;
    ReadFile(hFile, data.data(), (DWORD)data.size(), &bytesRead, NULL);
    CloseHandle(hFile);
    return data;
}
```

### Write file

```cpp
bool write_file(const wchar_t* path, const void* data, DWORD size) {
    HANDLE hFile = CreateFileW(path, GENERIC_WRITE, 0,
        NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hFile == INVALID_HANDLE_VALUE) return false;

    DWORD written;
    BOOL ok = WriteFile(hFile, data, size, &written, NULL);
    CloseHandle(hFile);
    return ok && written == size;
}
```

### CreateFile access patterns

| Scenario | dwDesiredAccess | dwShareMode | dwCreationDisposition |
|----------|----------------|-------------|----------------------|
| Read existing | `GENERIC_READ` | `FILE_SHARE_READ` | `OPEN_EXISTING` |
| Write new | `GENERIC_WRITE` | `0` | `CREATE_ALWAYS` |
| Append | `FILE_APPEND_DATA` | `FILE_SHARE_READ` | `OPEN_ALWAYS` |
| Read/write | `GENERIC_READ \| GENERIC_WRITE` | `0` | `OPEN_EXISTING` |
| Exclusive lock | `GENERIC_READ` | `0` | `OPEN_EXISTING` |

## 2. Memory-Mapped Files

### Map file for reading

```cpp
class MappedFile {
    HANDLE hFile_ = INVALID_HANDLE_VALUE;
    HANDLE hMap_ = nullptr;
    void* view_ = nullptr;
    size_t size_ = 0;
public:
    bool open(const wchar_t* path) {
        hFile_ = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ,
            NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
        if (hFile_ == INVALID_HANDLE_VALUE) return false;

        LARGE_INTEGER li;
        GetFileSizeEx(hFile_, &li);
        size_ = (size_t)li.QuadPart;

        hMap_ = CreateFileMappingW(hFile_, NULL, PAGE_READONLY, 0, 0, NULL);
        if (!hMap_) return false;

        view_ = MapViewOfFile(hMap_, FILE_MAP_READ, 0, 0, 0);
        return view_ != nullptr;
    }
    ~MappedFile() {
        if (view_) UnmapViewOfFile(view_);
        if (hMap_) CloseHandle(hMap_);
        if (hFile_ != INVALID_HANDLE_VALUE) CloseHandle(hFile_);
    }
    const void* data() const { return view_; }
    size_t size() const { return size_; }
};
```

### Named shared memory (anonymous mapping)

```cpp
// See ipc-and-networking.md § "Shared Memory" for cross-process usage
// Use INVALID_HANDLE_VALUE instead of a real file handle
HANDLE hMap = CreateFileMappingW(INVALID_HANDLE_VALUE, NULL,
    PAGE_READWRITE, 0, size, L"Local\\MySharedData");
```

## 3. Async I/O (Overlapped)

### Overlapped read

```cpp
HANDLE hFile = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ,
    NULL, OPEN_EXISTING, FILE_FLAG_OVERLAPPED, NULL);

OVERLAPPED ov = {};
ov.hEvent = CreateEventW(NULL, TRUE, FALSE, NULL);

char buf[4096];
ReadFile(hFile, buf, sizeof(buf), NULL, &ov);

// Do other work...

// Wait for completion
DWORD bytesRead;
GetOverlappedResult(hFile, &ov, &bytesRead, TRUE); // TRUE = wait

CloseHandle(ov.hEvent);
CloseHandle(hFile);
```

### Overlapped with completion routine (APC)

```cpp
void CALLBACK on_read_done(DWORD err, DWORD bytesRead, LPOVERLAPPED ov) {
    // Process completed read
    auto* ctx = (ReadContext*)ov->hEvent; // Repurpose hEvent for context
    ctx->handle_result(bytesRead);
}

ReadFileEx(hFile, buf, sizeof(buf), &ov, on_read_done);
// Thread must enter alertable wait for APC to fire
SleepEx(INFINITE, TRUE);
```

## 4. I/O Completion Ports (IOCP)

The highest-performance async I/O model on Windows. Ideal for servers with many concurrent connections.

### Create IOCP and associate handles

```cpp
// Create completion port
HANDLE hIocp = CreateIoCompletionPort(INVALID_HANDLE_VALUE, NULL, 0, 0);
// 0 threads = one per CPU core

// Associate a socket/file handle with the port
CreateIoCompletionPort((HANDLE)clientSocket, hIocp,
    (ULONG_PTR)perSocketContext, 0);
```

### Worker thread loop

```cpp
void iocp_worker(HANDLE hIocp) {
    while (true) {
        DWORD bytesTransferred;
        ULONG_PTR key;
        OVERLAPPED* ov;

        BOOL ok = GetQueuedCompletionStatus(
            hIocp, &bytesTransferred, &key, &ov, INFINITE);

        if (!ok && !ov) break; // Port closed or error

        auto* ctx = (PerIoContext*)ov;
        if (bytesTransferred == 0 && ctx->op == OP_READ) {
            // Client disconnected
            cleanup_client((PerSocketContext*)key);
            continue;
        }

        switch (ctx->op) {
        case OP_READ:
            process_data(ctx->buf, bytesTransferred);
            post_read(ctx);  // Issue next read
            break;
        case OP_WRITE:
            // Write completed
            break;
        }
    }
}
```

### Post custom completion

```cpp
// Wake worker thread with custom notification
PostQueuedCompletionStatus(hIocp, 0, SHUTDOWN_KEY, NULL);
```

### IOCP server skeleton

```cpp
struct PerIoContext {
    OVERLAPPED ov;
    WSABUF buf;
    char data[4096];
    enum { OP_READ, OP_WRITE } op;
};

void start_iocp_server(int port) {
    HANDLE hIocp = CreateIoCompletionPort(INVALID_HANDLE_VALUE, NULL, 0, 0);

    // Start worker threads (one per core)
    SYSTEM_INFO si;
    GetSystemInfo(&si);
    for (DWORD i = 0; i < si.dwNumberOfProcessors; ++i) {
        std::thread(iocp_worker, hIocp).detach();
    }

    // Accept loop
    SOCKET listener = create_listen_socket(port);
    while (true) {
        SOCKET client = accept(listener, NULL, NULL);
        CreateIoCompletionPort((HANDLE)client, hIocp, (ULONG_PTR)client, 0);

        // Post initial read
        auto* ctx = new PerIoContext{};
        ctx->op = PerIoContext::OP_READ;
        ctx->buf = { sizeof(ctx->data), ctx->data };
        DWORD flags = 0;
        WSARecv(client, &ctx->buf, 1, NULL, &flags, &ctx->ov, NULL);
    }
}
```

## 5. Directory Watching

```cpp
void watch_directory(const wchar_t* dir_path) {
    HANDLE hDir = CreateFileW(dir_path, FILE_LIST_DIRECTORY,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        NULL, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, NULL);

    BYTE buf[4096];
    DWORD bytes;
    while (ReadDirectoryChangesW(hDir, buf, sizeof(buf), TRUE,
        FILE_NOTIFY_CHANGE_FILE_NAME | FILE_NOTIFY_CHANGE_LAST_WRITE |
        FILE_NOTIFY_CHANGE_DIR_NAME | FILE_NOTIFY_CHANGE_SIZE,
        &bytes, NULL, NULL))
    {
        auto* info = (FILE_NOTIFY_INFORMATION*)buf;
        do {
            std::wstring name(info->FileName,
                              info->FileNameLength / sizeof(WCHAR));
            switch (info->Action) {
            case FILE_ACTION_ADDED:    /* created */  break;
            case FILE_ACTION_REMOVED:  /* deleted */  break;
            case FILE_ACTION_MODIFIED: /* changed */  break;
            case FILE_ACTION_RENAMED_OLD_NAME: /* rename from */ break;
            case FILE_ACTION_RENAMED_NEW_NAME: /* rename to */   break;
            }
            if (info->NextEntryOffset == 0) break;
            info = (FILE_NOTIFY_INFORMATION*)((BYTE*)info + info->NextEntryOffset);
        } while (true);
    }
    CloseHandle(hDir);
}
```

## 6. File Enumeration

```cpp
void find_files(const wchar_t* pattern) {
    WIN32_FIND_DATAW fd;
    HANDLE hFind = FindFirstFileW(pattern, &fd);
    if (hFind == INVALID_HANDLE_VALUE) return;

    do {
        if (wcscmp(fd.cFileName, L".") == 0 || wcscmp(fd.cFileName, L"..") == 0)
            continue;

        bool is_dir = fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY;
        uint64_t size = ((uint64_t)fd.nFileSizeHigh << 32) | fd.nFileSizeLow;
        // process fd.cFileName, is_dir, size
    } while (FindNextFileW(hFind, &fd));

    FindClose(hFind);
}
```

## 7. Temporary Files

```cpp
wchar_t tempPath[MAX_PATH], tempFile[MAX_PATH];
GetTempPathW(MAX_PATH, tempPath);
GetTempFileNameW(tempPath, L"myapp", 0, tempFile);
// tempFile is a unique filename like "C:\Users\...\Temp\myapp1234.tmp"
```
