# IPC & Networking Patterns

## Table of Contents
1. Shared Memory
2. Named Pipes
3. Anonymous Pipes
4. Named Synchronization Objects
5. Winsock Networking

## 1. Shared Memory

### Create / open shared memory

```cpp
// Host (creates)
HANDLE hMap = CreateFileMappingW(INVALID_HANDLE_VALUE, NULL,
    PAGE_READWRITE, 0, buffer_size, L"Local\\MyApp-SharedMem");
void* ptr = MapViewOfFile(hMap, FILE_MAP_ALL_ACCESS, 0, 0, buffer_size);

// Client (opens)
HANDLE hMap = OpenFileMappingW(FILE_MAP_ALL_ACCESS, FALSE, L"Local\\MyApp-SharedMem");
void* ptr = MapViewOfFile(hMap, FILE_MAP_ALL_ACCESS, 0, 0, buffer_size);

// Cleanup (both sides)
UnmapViewOfFile(ptr);
CloseHandle(hMap);
```

### RAII wrapper

```cpp
class SharedMemory {
    HANDLE handle_ = nullptr;
    void* memory_ = nullptr;
    uint32_t size_;
public:
    SharedMemory(const wchar_t* name, uint32_t size, bool create = true)
        : size_(size)
    {
        if (create)
            handle_ = CreateFileMappingW(INVALID_HANDLE_VALUE, NULL,
                PAGE_READWRITE, 0, size, name);
        else
            handle_ = OpenFileMappingW(FILE_MAP_ALL_ACCESS, FALSE, name);

        if (handle_)
            memory_ = MapViewOfFile(handle_, FILE_MAP_ALL_ACCESS, 0, 0, size);
    }
    ~SharedMemory() {
        if (memory_) UnmapViewOfFile(memory_);
        if (handle_) CloseHandle(handle_);
    }
    void* data() const { return memory_; }
    uint32_t size() const { return size_; }
    bool valid() const { return memory_ != nullptr; }

    SharedMemory(const SharedMemory&) = delete;
    SharedMemory& operator=(const SharedMemory&) = delete;
};
```

### Name prefixes

- `Local\\` — visible within the same session (use for same-user IPC)
- `Global\\` — visible across all sessions (requires `SeCreateGlobalPrivilege`)

## 2. Named Pipes

### Server

```cpp
// Create pipe
HANDLE hPipe = CreateNamedPipeW(
    L"\\\\.\\pipe\\MyApp-Pipe",
    PIPE_ACCESS_DUPLEX,                             // bidirectional
    PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
    PIPE_UNLIMITED_INSTANCES,                       // max instances
    4096, 4096,                                     // out/in buffer sizes
    0, NULL);

// Wait for client connection (blocks)
ConnectNamedPipe(hPipe, NULL);

// Read/write
char buf[4096];
DWORD bytesRead, bytesWritten;
ReadFile(hPipe, buf, sizeof(buf), &bytesRead, NULL);
WriteFile(hPipe, response, responseLen, &bytesWritten, NULL);

// Disconnect and reuse for next client
DisconnectNamedPipe(hPipe);
// Loop back to ConnectNamedPipe...

CloseHandle(hPipe);
```

### Client

```cpp
HANDLE hPipe = CreateFileW(
    L"\\\\.\\pipe\\MyApp-Pipe",
    GENERIC_READ | GENERIC_WRITE,
    0, NULL, OPEN_EXISTING, 0, NULL);

if (hPipe == INVALID_HANDLE_VALUE) {
    if (GetLastError() == ERROR_PIPE_BUSY) {
        // Wait for pipe to become available
        WaitNamedPipeW(L"\\\\.\\pipe\\MyApp-Pipe", 5000);
        // Retry CreateFile...
    }
}

// Set message mode
DWORD mode = PIPE_READMODE_MESSAGE;
SetNamedPipeHandleState(hPipe, &mode, NULL, NULL);

// Read/write
DWORD bytesWritten, bytesRead;
WriteFile(hPipe, request, requestLen, &bytesWritten, NULL);
ReadFile(hPipe, buf, sizeof(buf), &bytesRead, NULL);

CloseHandle(hPipe);
```

### Multi-client server pattern

```cpp
void pipe_server_loop() {
    while (running) {
        HANDLE hPipe = CreateNamedPipeW(L"\\\\.\\pipe\\MyApp-Pipe",
            PIPE_ACCESS_DUPLEX,
            PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
            PIPE_UNLIMITED_INSTANCES, 4096, 4096, 0, NULL);

        if (ConnectNamedPipe(hPipe, NULL) || GetLastError() == ERROR_PIPE_CONNECTED) {
            // Spawn worker thread for this client
            std::thread([hPipe] {
                handle_client(hPipe);
                DisconnectNamedPipe(hPipe);
                CloseHandle(hPipe);
            }).detach();
        }
    }
}
```

## 3. Anonymous Pipes

For parent-child process communication (one-directional):

```cpp
HANDLE hRead, hWrite;
SECURITY_ATTRIBUTES sa = { sizeof(sa), NULL, TRUE };
CreatePipe(&hRead, &hWrite, &sa, 0);

// Parent keeps hRead, passes hWrite to child via STARTUPINFO
// See threads-and-processes.md § "Redirect child stdout/stderr"
```

## 4. Named Synchronization Objects

### Events (cross-process signaling)

```cpp
// Creator
HANDLE evt = CreateEventW(NULL,
    FALSE,    // FALSE = auto-reset (resets after one WaitFor succeeds)
    FALSE,    // Initially non-signaled
    L"Local\\MyApp-DataReady");

// Opener (other process)
HANDLE evt = OpenEventW(SYNCHRONIZE | EVENT_MODIFY_STATE, FALSE,
    L"Local\\MyApp-DataReady");

SetEvent(evt);   // Signal (wake one waiter for auto-reset)
ResetEvent(evt); // Manual-reset only — explicit reset
```

### Mutexes (cross-process locking)

```cpp
HANDLE mtx = CreateMutexW(NULL, FALSE, L"Local\\MyApp-Lock");
// FALSE = not initially owned

WaitForSingleObject(mtx, INFINITE);  // Acquire
// ... critical section ...
ReleaseMutex(mtx);                   // Release
```

### Semaphores (cross-process counting)

```cpp
HANDLE sem = CreateSemaphoreW(NULL, 0, 100, L"Local\\MyApp-Sem");
// Initial count = 0, max = 100

ReleaseSemaphore(sem, 1, NULL);       // +1
WaitForSingleObject(sem, INFINITE);   // -1 (blocks at 0)
```

### WaitForMultipleObjects

```cpp
HANDLE handles[] = { event1, event2, processHandle };
DWORD r = WaitForMultipleObjects(_countof(handles), handles, FALSE, timeout_ms);
switch (r) {
case WAIT_OBJECT_0:     /* event1 */          break;
case WAIT_OBJECT_0 + 1: /* event2 */          break;
case WAIT_OBJECT_0 + 2: /* process exited */  break;
case WAIT_TIMEOUT:      /* timed out */       break;
case WAIT_FAILED:       /* error */           break;
}
```

## 5. Winsock Networking

### Initialization

```cpp
#include <WinSock2.h>
#include <WS2tcpip.h>
#pragma comment(lib, "Ws2_32.lib")

// Startup (once per process)
WSADATA wsa;
WSAStartup(MAKEWORD(2, 2), &wsa);

// Cleanup
WSACleanup();
```

### TCP server

```cpp
SOCKET listener = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);

sockaddr_in addr = {};
addr.sin_family = AF_INET;
addr.sin_addr.s_addr = INADDR_ANY;
addr.sin_port = htons(8080);

bind(listener, (sockaddr*)&addr, sizeof(addr));
listen(listener, SOMAXCONN);

while (true) {
    sockaddr_in client_addr;
    int len = sizeof(client_addr);
    SOCKET client = accept(listener, (sockaddr*)&client_addr, &len);
    if (client == INVALID_SOCKET) break;

    // Handle client (spawn thread or use IOCP)
    std::thread(handle_client, client).detach();
}
closesocket(listener);
```

### TCP client

```cpp
SOCKET sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);

// Resolve hostname
addrinfo hints = {}, *result;
hints.ai_family = AF_INET;
hints.ai_socktype = SOCK_STREAM;
getaddrinfo("example.com", "80", &hints, &result);

connect(sock, result->ai_addr, (int)result->ai_addrlen);
freeaddrinfo(result);

// Send/receive
send(sock, data, data_len, 0);
int received = recv(sock, buf, buf_size, 0);

closesocket(sock);
```

### Non-blocking with select

```cpp
u_long mode = 1;
ioctlsocket(sock, FIONBIO, &mode); // Non-blocking

fd_set read_set, write_set;
FD_ZERO(&read_set);
FD_SET(sock, &read_set);

timeval tv = { 0, 100000 }; // 100ms
int ready = select(0, &read_set, &write_set, NULL, &tv);
if (ready > 0 && FD_ISSET(sock, &read_set)) {
    int n = recv(sock, buf, sizeof(buf), 0);
}
```

### UDP

```cpp
SOCKET sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);

sockaddr_in addr = {};
addr.sin_family = AF_INET;
addr.sin_port = htons(9000);
addr.sin_addr.s_addr = INADDR_ANY;
bind(sock, (sockaddr*)&addr, sizeof(addr));

// Receive
sockaddr_in from;
int fromLen = sizeof(from);
int n = recvfrom(sock, buf, sizeof(buf), 0, (sockaddr*)&from, &fromLen);

// Send
sendto(sock, data, len, 0, (sockaddr*)&dest, sizeof(dest));

closesocket(sock);
```
