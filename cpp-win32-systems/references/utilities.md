# Utilities

## Table of Contents
1. Console API
2. Debugging Helpers
3. Environment Variables

## 1. Console API

### Allocate console for GUI app

```cpp
AllocConsole();
FILE* fp;
freopen_s(&fp, "CONOUT$", "w", stdout);
freopen_s(&fp, "CONOUT$", "w", stderr);
freopen_s(&fp, "CONIN$", "r", stdin);
```

### Ctrl+C handler

```cpp
BOOL WINAPI console_handler(DWORD ctrl) {
    switch (ctrl) {
    case CTRL_C_EVENT:
    case CTRL_BREAK_EVENT:
    case CTRL_CLOSE_EVENT:
        g_running = false;
        return TRUE; // Handled
    }
    return FALSE;
}
SetConsoleCtrlHandler(console_handler, TRUE);
```

### Console colors

```cpp
HANDLE hCon = GetStdHandle(STD_OUTPUT_HANDLE);
SetConsoleTextAttribute(hCon, FOREGROUND_RED | FOREGROUND_INTENSITY);
printf("Error!\n");
SetConsoleTextAttribute(hCon, FOREGROUND_RED | FOREGROUND_GREEN | FOREGROUND_BLUE);
```

## 2. Debugging Helpers

```cpp
// Output to debugger (visible in VS Output window / DbgView)
OutputDebugStringW(L"Debug message\n");

// Check if debugger attached
if (IsDebuggerPresent()) {
    DebugBreak(); // Trigger breakpoint
}

// Performance measurement
LARGE_INTEGER freq, start, end;
QueryPerformanceFrequency(&freq);
QueryPerformanceCounter(&start);
do_work();
QueryPerformanceCounter(&end);
double ms = (end.QuadPart - start.QuadPart) * 1000.0 / freq.QuadPart;
```

## 3. Environment Variables

```cpp
// Read
WCHAR buf[32768];
DWORD len = GetEnvironmentVariableW(L"PATH", buf, _countof(buf));
std::wstring path(buf, len);

// Set (current process only)
SetEnvironmentVariableW(L"MY_VAR", L"value");

// Delete
SetEnvironmentVariableW(L"MY_VAR", NULL);

// Expand (resolve %VAR% references)
WCHAR expanded[MAX_PATH];
ExpandEnvironmentStringsW(L"%USERPROFILE%\\Documents", expanded, MAX_PATH);
```
