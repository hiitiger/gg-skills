# Window & GUI — Decisions & Pitfalls

## Per-Window State

WndProc is a free function with no `this`. Pass your state pointer through `CreateWindowExW`'s last param (`lpCreateParams`), store it in `GWLP_USERDATA` during `WM_CREATE`, retrieve with `GetWindowLongPtrW`. This avoids globals and supports multiple windows.

## Message Loop — Which One?

- **`GetMessage` loop** — blocks until message arrives, low CPU when idle. Use for standard desktop apps.
- **`PeekMessage` loop** — runs continuously. Use for games/animations that render every frame.
- **`MsgWaitForMultipleObjects` loop** — waits for messages OR kernel events. Use when mixing UI with worker threads or async I/O.
- **With accelerator table** — wrap `TranslateAcceleratorW` before `TranslateMessage`/`DispatchMessage`.

## Common Pitfalls

- **`SendMessage` from worker thread → deadlock.** It blocks until WndProc returns. If the UI thread is waiting on the worker, both stall. Always use `PostMessage` for cross-thread communication.
- **Custom messages**: use `WM_APP + N` range, not `WM_USER + N` (which collides with control-specific messages).
- **GDI double buffering**: must `SelectObject(memDC, oldBmp)` before `DeleteObject(memBmp)` — deleting a GDI object while selected into a DC leaks it.
- **`BeginPaint`/`EndPaint`** must always be paired in `WM_PAINT`. Skipping `BeginPaint` causes infinite `WM_PAINT` messages.

## DPI Awareness

Without DPI awareness, Windows bitmap-scales your app — blurry on high-DPI. Call `SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)` before creating any window. Handle `WM_DPICHANGED` to resize using the suggested `RECT*` in lParam. Scale values with `MulDiv(logical, dpi, 96)`.

## Window Subclassing

Replaces a window's WndProc to intercept messages without owning the window class. Always call `CallWindowProcW` for unhandled messages. Remember to restore the original proc before destruction.

## Style Quick Reference

- `WS_EX_LAYERED` — for alpha/transparency (`SetLayeredWindowAttributes`)
- `WS_EX_TOPMOST` — always on top
- `WS_EX_NOACTIVATE` — doesn't steal focus
- `WS_EX_TOOLWINDOW` — excluded from taskbar
