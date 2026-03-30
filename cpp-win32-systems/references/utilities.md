# Utilities — Quick Reference

## Console

- `AllocConsole()` + `freopen_s` to attach stdout/stderr to a console from a GUI app.
- `SetConsoleCtrlHandler` to catch Ctrl+C / Ctrl+Break / close events. Return `TRUE` to mark as handled.

## Debugging

- `OutputDebugStringW` — visible in VS Output window or DbgView.
- `IsDebuggerPresent()` + `DebugBreak()` to conditionally trigger a breakpoint.
- `QueryPerformanceCounter` / `QueryPerformanceFrequency` for high-resolution timing.

## Environment Variables

- `GetEnvironmentVariableW` / `SetEnvironmentVariableW` — current process only.
- `ExpandEnvironmentStringsW` to resolve `%VAR%` references in paths.
- Pass `NULL` as value to `SetEnvironmentVariableW` to delete.
