# Hooks & Inspection — Decisions & Pitfalls

## API Hooking — Which Method?

| Method | When to Use | Dependency |
|--------|------------|------------|
| **Detours** | Inline hook any function by address | Microsoft Detours library (`vcpkg install detours`) |
| **VTable patching** | Hook virtual/COM methods by vtable index | None, but must `VirtualProtect` the vtable page |
| **`SetWindowsHookEx`** | Monitor window messages system-wide | Requires message loop on the installing thread |

### Detours

- `DetourTransactionBegin` → `DetourUpdateThread` → `DetourAttach` → `DetourTransactionCommit`. Same for detach.
- The original function pointer becomes a trampoline — call it from your hook to invoke the original.

### SetWindowsHookEx

- Low-level hooks (`WH_KEYBOARD_LL`, `WH_MOUSE_LL`) run in the installing thread's context. That thread MUST have a running message loop.
- `CallNextHookEx` is required — skipping it breaks other hooks in the chain.
- `SetWindowsHookEx(WH_GETMESSAGE, ...)` with a target thread is a safe DLL injection method (see system-and-services.md § DLL Injection).
