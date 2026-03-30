# System & Services — Decisions & Pitfalls

## DLL

### DllMain Loader-Lock Rules

DllMain runs under the OS loader lock. Any call that directly or indirectly acquires the loader lock will deadlock:
- `LoadLibrary` / `FreeLibrary` (acquires loader lock)
- `CoInitialize` or any COM (loads DLLs internally)
- `WaitForSingleObject` on threads (the thread may be waiting for the loader lock)
- Registry, socket, stdio, heap-heavy ops (may load DLLs on first use)

Keep DllMain minimal: set flags, call `DisableThreadLibraryCalls`, return.

### DLL Injection (Safe Method)

Use `SetWindowsHookEx(WH_GETMESSAGE, exported_proc, hModule, target_thread_id)` + `PostThreadMessage` to trigger. This is safer than `CreateRemoteThread` — uses the OS hook mechanism, no need for `PROCESS_CREATE_THREAD` rights. The target thread loads your DLL on next message dispatch.

**Prevent premature unload**: In `DLL_PROCESS_ATTACH`, call `LoadLibraryW` on your own DLL name to add a reference — otherwise the hook owner can `UnhookWindowsHookEx` and your DLL disappears from under you.

### Injected DLL Build Rules

- **Static link CRT** (`/MT`, `/MTd`) — the target process may have a different CRT version. Sharing CRT across DLL boundaries causes heap corruption.
- `DisableThreadLibraryCalls(hinstDLL)` in DllMain — avoids unnecessary attach/detach calls per thread.
- `DONT_RESOLVE_DLL_REFERENCES` flag with `LoadLibraryExW` to probe a DLL without executing DllMain.

### Exporting

- `__declspec(dllexport)` with `extern "C"` for simple exports.
- `.def` file for stable ordinals across versions.

### Delay Loading

Defers DLL load until first function call — useful for optional dependencies or faster startup. `/DELAYLOAD:lib.dll` + `delayimp.lib`. Catch `VcppException(ERROR_SEVERITY_ERROR, ERROR_MOD_NOT_FOUND)` with SEH if the DLL might be absent.

## COM

### STA vs MTA

- **STA** (`COINIT_APARTMENTTHREADED`) — serializes COM calls to one thread. Required for UI, OLE, Shell dialogs, and most desktop COM objects.
- **MTA** (`COINIT_MULTITHREADED`) — concurrent calls from any thread. Use for background/server work.
- Mismatching causes crashes or silent cross-apartment marshaling overhead.
- Rule of thumb: STA for main/UI thread, MTA for worker threads.

### ComPtr

Use `Microsoft::WRL::ComPtr<T>`. Key methods: `.Get()` for raw pointer, `.GetAddressOf()` for out-param, `.As(&other)` for QueryInterface, `IID_PPV_ARGS(p.GetAddressOf())` for creation.

## Windows Services

- `ServiceMain` registers the control handler, reports `SERVICE_RUNNING`, enters work loop, reports `SERVICE_STOPPED` on exit.
- `ServiceCtrlHandler` handles `SERVICE_CONTROL_STOP` — set state to `SERVICE_STOP_PENDING` and signal your work loop to exit.
- Install with `CreateServiceW` via `SC_MANAGER_CREATE_SERVICE`.

## Registry Pitfalls

- `RegCreateKeyExW` creates the key if it doesn't exist — use `RegOpenKeyExW` for read-only access.
- `KEY_ALL_ACCESS` requires admin — use `KEY_READ` or `KEY_WRITE` for least privilege.
- Always `RegCloseKey` — wrap in RAII.

## UAC / Elevation

- Check with `OpenProcessToken` + `TokenElevation`.
- Re-launch elevated with `ShellExecuteExW` using `lpVerb = L"runas"`.
- Embed manifest with `requestedExecutionLevel` for apps that always need admin.
