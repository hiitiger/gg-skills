# IPC & Networking — Decisions & Pitfalls

## Choosing an IPC Mechanism

| Mechanism | Best For | Trade-off |
|-----------|----------|-----------|
| **Shared Memory** | Large data buffers, lowest latency | Must coordinate access yourself (named mutex/event) |
| **Named Pipes** | Request-response, stream messaging | Built-in message framing and ACL security, no port management |
| **Anonymous Pipes** | Parent-child stdout/stderr redirect | One-directional only |
| **Winsock** | Network communication, cross-machine | More setup, no built-in message boundaries for TCP |
| **Named Events/Mutexes** | Simple cross-process signaling | No data transfer, just synchronization |

## Named Object Rules

- **`Local\\` prefix** — visible within same session (same-user IPC)
- **`Global\\` prefix** — visible across all sessions (requires `SeCreateGlobalPrivilege`, typically services)
- **NULL `SECURITY_ATTRIBUTES`** = same-user only. Build explicit security descriptor for cross-user access.
- **Name collisions** are real — use unique prefixes like `Local\\MyCompany-MyApp-`.

## Named Pipes Pitfalls

- `PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE` for request-response protocols — without this, data arrives as a byte stream with no boundaries.
- Client gets `ERROR_PIPE_BUSY` when all instances are in use — call `WaitNamedPipeW` and retry.
- Multi-client: create a new pipe instance per client in the accept loop, handle each on a worker thread (or use IOCP for overlapped pipes).

## Winsock Pitfalls

- Use `closesocket()`, not `close()` — `close()` silently does nothing on a `SOCKET`.
- `recv()` returning 0 = graceful close by remote peer, not "no data".
- `recv()` returning `SOCKET_ERROR` with `WSAEWOULDBLOCK` on non-blocking sockets is normal — retry.
- Always pair `getaddrinfo()` with `freeaddrinfo()`.
- For high-performance async sockets → IOCP (see io-and-filesystem.md).
