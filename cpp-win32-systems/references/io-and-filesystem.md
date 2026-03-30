# I/O & File System — Decisions & Pitfalls

## Choosing an I/O Model

- **Synchronous** — fine for simple tools, few concurrent operations, or when you block anyway.
- **Overlapped + event** — moderate concurrency on a single thread. Limited to ~64 handles per `WaitForMultipleObjects` call.
- **IOCP** — high-concurrency servers (hundreds+ sockets/files). Multiplexes many I/O ops onto a small thread pool, avoiding 1-thread-per-connection.

## File I/O Pitfalls

- Always wrap `CreateFileW` handles in `UniqueHandle`.
- `CreateFileW` returns `INVALID_HANDLE_VALUE` on failure (not `NULL`) — check accordingly.
- `FILE_SHARE_READ` lets others read while you have the file open. `0` = exclusive lock.
- `FILE_FLAG_OVERLAPPED` must be set at open time for async I/O — you can't switch later.

## Memory-Mapped Files

Two uses: (1) map a real file for fast read-only access, (2) `INVALID_HANDLE_VALUE` + a name for cross-process shared memory (see ipc-and-networking.md).

Always `UnmapViewOfFile` before `CloseHandle` on the mapping.

## IOCP Key Points

- `CreateIoCompletionPort` both creates the port and associates handles to it.
- Worker threads call `GetQueuedCompletionStatus` in a loop — one thread per core is typical.
- `bytesTransferred == 0` on a read = client disconnected (for sockets).
- `PostQueuedCompletionStatus` with a sentinel key to signal worker shutdown.
- Embed `OVERLAPPED` as the first member of your per-I/O context struct — cast back in the worker.

## Directory Watching

- `ReadDirectoryChangesW` requires `FILE_FLAG_BACKUP_SEMANTICS` on the directory handle.
- Set `TRUE` for `bWatchSubtree` to watch recursively.
- Walk `FILE_NOTIFY_INFORMATION` linked list via `NextEntryOffset`.
- For production, use overlapped mode — synchronous blocks the thread.

## File Enumeration

- `FindFirstFileW` / `FindNextFileW` / `FindClose` — not a regular HANDLE, `CloseHandle()` won't work.
- Always skip `.` and `..` entries.
