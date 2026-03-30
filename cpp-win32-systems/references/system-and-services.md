# System & Services Patterns

## Table of Contents
1. DLL Patterns
2. COM Patterns
3. Windows Services
4. Registry Operations
5. Shell API & File Dialogs
6. UAC & Elevation
7. Module Enumeration
8. API Hooking

## 1. DLL Patterns

### DllMain

```cpp
BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved) {
    switch (fdwReason) {
    case DLL_PROCESS_ATTACH:
        DisableThreadLibraryCalls(hinstDLL); // Optimization
        break;
    case DLL_PROCESS_DETACH:
        break;
    }
    return TRUE;
}
```

**Loader-lock rules** — never do these in DllMain:
- `LoadLibrary` / `FreeLibrary`
- `CoInitialize` or any COM
- `WaitForSingleObject` on threads
- Registry, socket, stdio, heap-heavy operations

### Exporting functions

```cpp
// Method 1: declspec (simple)
extern "C" __declspec(dllexport) int my_api(const char* input);

// Method 2: .def file (stable ordinals)
// mylib.def:
// EXPORTS
//     my_api @1
//     my_init @2
```

### Runtime loading (plugins)

```cpp
HMODULE lib = LoadLibraryW(L"plugin.dll");
if (!lib) { /* GetLastError() */ }

auto fn = (int(*)(const char*))GetProcAddress(lib, "my_api");
if (fn) {
    int result = fn("hello");
}
FreeLibrary(lib);
```

### Delay loading

```cmake
# CMake
target_link_options(myapp PRIVATE /DELAYLOAD:optional_lib.dll)
target_link_libraries(myapp delayimp)
```

```cpp
// Check availability at runtime
__try {
    optional_function();
} __except (GetExceptionCode() == VcppException(ERROR_SEVERITY_ERROR, ERROR_MOD_NOT_FOUND)
            ? EXCEPTION_EXECUTE_HANDLER : EXCEPTION_CONTINUE_SEARCH) {
    // DLL not available
}
```

## 2. COM Patterns

### Initialization

```cpp
// STA (single-threaded apartment) — for UI, OLE, Shell
CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);

// MTA (multi-threaded apartment) — for background/server
CoInitializeEx(nullptr, COINIT_MULTITHREADED);

// Always pair with:
CoUninitialize();
```

### ComPtr lifetime management

```cpp
#include <wrl/client.h>
using Microsoft::WRL::ComPtr;

ComPtr<IUnknown> obj;
HRESULT hr = CoCreateInstance(CLSID_Something, nullptr,
    CLSCTX_INPROC_SERVER, IID_PPV_ARGS(obj.GetAddressOf()));

// QueryInterface
ComPtr<ISpecific> specific;
hr = obj.As(&specific);

// Pass to function expecting raw pointer
use_raw(specific.Get());

// Pass to function that fills a pointer
other_func(specific.ReleaseAndGetAddressOf());
```

### Common HRESULT values

| HRESULT | Meaning |
|---------|---------|
| `S_OK` (0) | Success |
| `S_FALSE` (1) | Success, but no effect |
| `E_FAIL` | Generic failure |
| `E_INVALIDARG` | Invalid parameter |
| `E_OUTOFMEMORY` | Out of memory |
| `E_NOINTERFACE` | Interface not supported |
| `E_NOTIMPL` | Not implemented |
| `DXGI_ERROR_DEVICE_REMOVED` | GPU device lost |

## 3. Windows Services

### Service skeleton

```cpp
static SERVICE_STATUS_HANDLE g_hStatus;
static SERVICE_STATUS g_status;
static bool g_running = true;

void WINAPI ServiceCtrlHandler(DWORD ctrl) {
    switch (ctrl) {
    case SERVICE_CONTROL_STOP:
        g_status.dwCurrentState = SERVICE_STOP_PENDING;
        SetServiceStatus(g_hStatus, &g_status);
        g_running = false;
        break;
    case SERVICE_CONTROL_INTERROGATE:
        SetServiceStatus(g_hStatus, &g_status);
        break;
    }
}

void WINAPI ServiceMain(DWORD argc, LPWSTR* argv) {
    g_hStatus = RegisterServiceCtrlHandlerW(L"MySvc", ServiceCtrlHandler);

    g_status = {};
    g_status.dwServiceType = SERVICE_WIN32_OWN_PROCESS;
    g_status.dwCurrentState = SERVICE_RUNNING;
    g_status.dwControlsAccepted = SERVICE_ACCEPT_STOP;
    SetServiceStatus(g_hStatus, &g_status);

    while (g_running) {
        do_service_work();
        Sleep(1000);
    }

    g_status.dwCurrentState = SERVICE_STOPPED;
    SetServiceStatus(g_hStatus, &g_status);
}

int wmain() {
    SERVICE_TABLE_ENTRYW table[] = {
        { (LPWSTR)L"MySvc", ServiceMain },
        { NULL, NULL }
    };
    StartServiceCtrlDispatcherW(table);
}
```

### Install / uninstall service

```cpp
void install_service(const wchar_t* exe_path) {
    SC_HANDLE scm = OpenSCManagerW(NULL, NULL, SC_MANAGER_CREATE_SERVICE);
    SC_HANDLE svc = CreateServiceW(scm, L"MySvc", L"My Service",
        SERVICE_ALL_ACCESS, SERVICE_WIN32_OWN_PROCESS,
        SERVICE_AUTO_START, SERVICE_ERROR_NORMAL,
        exe_path, NULL, NULL, NULL, NULL, NULL);
    CloseServiceHandle(svc);
    CloseServiceHandle(scm);
}

void uninstall_service() {
    SC_HANDLE scm = OpenSCManagerW(NULL, NULL, SC_MANAGER_CONNECT);
    SC_HANDLE svc = OpenServiceW(scm, L"MySvc", DELETE);
    DeleteService(svc);
    CloseServiceHandle(svc);
    CloseServiceHandle(scm);
}
```

## 4. Registry Operations

### RAII key wrapper

```cpp
class RegKey {
    HKEY key_ = nullptr;
public:
    RegKey(HKEY root, const wchar_t* path, REGSAM access = KEY_ALL_ACCESS) {
        RegCreateKeyExW(root, path, 0, NULL, 0, access, NULL, &key_, NULL);
    }
    ~RegKey() { if (key_) RegCloseKey(key_); }
    operator HKEY() const { return key_; }
    bool valid() const { return key_ != nullptr; }
};
```

### Read/write values

```cpp
// Write DWORD
void reg_set_dword(HKEY root, const wchar_t* path,
                   const wchar_t* name, DWORD value) {
    RegKey key(root, path, KEY_WRITE);
    if (key.valid())
        RegSetValueExW(key, name, 0, REG_DWORD, (BYTE*)&value, sizeof(value));
}

// Read string
std::wstring reg_get_string(HKEY root, const wchar_t* path,
                            const wchar_t* name) {
    HKEY key;
    if (RegOpenKeyExW(root, path, 0, KEY_READ, &key) != ERROR_SUCCESS) return {};
    WCHAR buf[512];
    DWORD size = sizeof(buf), type;
    RegQueryValueExW(key, name, NULL, &type, (BYTE*)buf, &size);
    RegCloseKey(key);
    return (type == REG_SZ) ? std::wstring(buf) : std::wstring{};
}

// Delete value
void reg_delete(HKEY root, const wchar_t* path, const wchar_t* name) {
    HKEY key;
    if (RegOpenKeyExW(root, path, 0, KEY_WRITE, &key) == ERROR_SUCCESS) {
        RegDeleteValueW(key, name);
        RegCloseKey(key);
    }
}

// Enumerate subkeys
void reg_enum_keys(HKEY root, const wchar_t* path) {
    HKEY key;
    if (RegOpenKeyExW(root, path, 0, KEY_READ, &key) != ERROR_SUCCESS) return;
    WCHAR name[256];
    for (DWORD i = 0; ; ++i) {
        DWORD len = 256;
        if (RegEnumKeyExW(key, i, name, &len, NULL, NULL, NULL, NULL) != ERROR_SUCCESS)
            break;
    }
    RegCloseKey(key);
}
```

## 5. Shell API & File Dialogs

### Open file / URL

```cpp
// Open URL in default browser
ShellExecuteW(NULL, L"open", L"https://example.com", NULL, NULL, SW_SHOW);

// Open file with associated application
ShellExecuteW(NULL, L"open", L"C:\\doc.pdf", NULL, NULL, SW_SHOW);

// Open folder in Explorer
ShellExecuteW(NULL, L"explore", L"C:\\MyFolder", NULL, NULL, SW_SHOW);
```

### File open dialog (COM-based, Vista+)

```cpp
ComPtr<IFileOpenDialog> dlg;
CoCreateInstance(CLSID_FileOpenDialog, NULL, CLSCTX_ALL,
    IID_PPV_ARGS(dlg.GetAddressOf()));

COMDLG_FILTERSPEC filters[] = {
    { L"Text Files", L"*.txt" },
    { L"All Files", L"*.*" }
};
dlg->SetFileTypes(_countof(filters), filters);

if (dlg->Show(hwnd) == S_OK) {
    ComPtr<IShellItem> item;
    dlg->GetResult(item.GetAddressOf());
    PWSTR path;
    item->GetDisplayName(SIGDN_FILESYSPATH, &path);
    // Use path...
    CoTaskMemFree(path);
}
```

### Known folders

```cpp
#include <ShlObj.h>

PWSTR path;
SHGetKnownFolderPath(FOLDERID_Desktop, 0, NULL, &path);
// path = "C:\Users\...\Desktop"
CoTaskMemFree(path);

// Common folder IDs:
// FOLDERID_Desktop, FOLDERID_Documents, FOLDERID_Downloads,
// FOLDERID_LocalAppData, FOLDERID_RoamingAppData,
// FOLDERID_ProgramData, FOLDERID_ProgramFiles
```

## 6. UAC & Elevation

### Check if running as admin

```cpp
bool is_elevated() {
    BOOL elevated = FALSE;
    HANDLE token;
    if (OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &token)) {
        TOKEN_ELEVATION te;
        DWORD size;
        GetTokenInformation(token, TokenElevation, &te, sizeof(te), &size);
        elevated = te.TokenIsElevated;
        CloseHandle(token);
    }
    return elevated;
}
```

### Re-launch elevated

```cpp
void relaunch_as_admin() {
    WCHAR path[MAX_PATH];
    GetModuleFileNameW(NULL, path, MAX_PATH);

    SHELLEXECUTEINFOW sei = { sizeof(sei) };
    sei.lpVerb = L"runas";
    sei.lpFile = path;
    sei.nShow = SW_SHOW;
    ShellExecuteExW(&sei);
}
```

### Application manifest (require admin)

```xml
<!-- app.manifest embedded in exe -->
<trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
  <security>
    <requestedPrivileges>
      <requestedExecutionLevel level="requireAdministrator" uiAccess="false"/>
    </requestedPrivileges>
  </security>
</trustInfo>
```

```cmake
# CMake: embed manifest
set_target_properties(myapp PROPERTIES LINK_FLAGS "/MANIFEST:EMBED /MANIFESTINPUT:app.manifest")
```

## 7. Module Enumeration

### Toolhelp32 — walk loaded modules

```cpp
#include <TlHelp32.h>

void enum_modules(DWORD pid) {
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, pid);
    if (snap == INVALID_HANDLE_VALUE) return;

    MODULEENTRY32W me = { sizeof(me) };
    if (Module32FirstW(snap, &me)) {
        do {
            // me.szModule    — "ntdll.dll"
            // me.szExePath   — full path
            // me.modBaseAddr — base address
            // me.modBaseSize — image size
        } while (Module32NextW(snap, &me));
    }
    CloseHandle(snap);
}
```

### Check if module loaded

```cpp
bool is_loaded(const wchar_t* name) {
    return GetModuleHandleW(name) != nullptr;
}
```

## 8. API Hooking

### Detours (inline hooking)

```cpp
#include <detours.h>

static auto Real_Fn = TargetFunction;

auto WINAPI My_Fn(/* same params */) {
    // pre-hook logic
    auto result = Real_Fn(/* params */);
    // post-hook logic
    return result;
}

void install() {
    DetourTransactionBegin();
    DetourUpdateThread(GetCurrentThread());
    DetourAttach(&(PVOID&)Real_Fn, My_Fn);
    DetourTransactionCommit();
}

void remove() {
    DetourTransactionBegin();
    DetourUpdateThread(GetCurrentThread());
    DetourDetach(&(PVOID&)Real_Fn, My_Fn);
    DetourTransactionCommit();
}
```

### VTable patching (COM objects)

```cpp
void* hook_vtable(void* com_obj, size_t method_index, void* new_fn) {
    void** vtable = *(void***)com_obj;
    void* original = vtable[method_index];
    DWORD old_protect;
    VirtualProtect(&vtable[method_index], sizeof(void*),
                   PAGE_READWRITE, &old_protect);
    vtable[method_index] = new_fn;
    VirtualProtect(&vtable[method_index], sizeof(void*),
                   old_protect, &old_protect);
    return original;
}
```

### SetWindowsHookEx (system-wide message hooks)

```cpp
HHOOK hook = SetWindowsHookExW(WH_KEYBOARD_LL,
    [](int code, WPARAM wp, LPARAM lp) -> LRESULT {
        if (code >= 0) {
            auto* kb = (KBDLLHOOKSTRUCT*)lp;
            // kb->vkCode, kb->flags
        }
        return CallNextHookEx(NULL, code, wp, lp);
    }, GetModuleHandleW(NULL), 0);

// Requires message loop to be running
// Cleanup: UnhookWindowsHookEx(hook);
```

