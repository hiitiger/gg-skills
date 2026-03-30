# Window & GUI Patterns

## Table of Contents
1. Window Class & Creation
2. Per-Window State
3. Message Loop Patterns
4. Common Messages
5. Window Subclassing
6. GDI Drawing
7. DPI Awareness
8. Window Styles & Properties

## 1. Window Class & Creation

```cpp
LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp);

HWND create_main_window(HINSTANCE hInst, const wchar_t* title, int w, int h) {
    WNDCLASSEXW wc = { sizeof(wc) };
    wc.lpfnWndProc   = WndProc;
    wc.hInstance      = hInst;
    wc.hCursor        = LoadCursor(NULL, IDC_ARROW);
    wc.hbrBackground  = (HBRUSH)(COLOR_WINDOW + 1);
    wc.lpszClassName  = L"MyWindowClass";
    wc.hIcon          = LoadIcon(NULL, IDI_APPLICATION);
    RegisterClassExW(&wc);

    // Adjust rect to account for title bar and borders
    RECT rc = { 0, 0, w, h };
    AdjustWindowRectEx(&rc, WS_OVERLAPPEDWINDOW, FALSE, 0);

    return CreateWindowExW(
        0, wc.lpszClassName, title,
        WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT, CW_USEDEFAULT,
        rc.right - rc.left, rc.bottom - rc.top,
        NULL, NULL, hInst, nullptr);  // last param → WM_CREATE's CREATESTRUCT::lpCreateParams
}
```

## 2. Per-Window State

```cpp
// Pass state pointer via CreateWindowEx lpParam
HWND hwnd = CreateWindowExW(0, cls, title, style,
    x, y, w, h, NULL, NULL, hInst, (LPVOID)my_app_state);

// Retrieve in WndProc
LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    AppState* app = (AppState*)GetWindowLongPtrW(hwnd, GWLP_USERDATA);

    switch (msg) {
    case WM_CREATE: {
        auto* cs = (CREATESTRUCTW*)lp;
        app = (AppState*)cs->lpCreateParams;
        SetWindowLongPtrW(hwnd, GWLP_USERDATA, (LONG_PTR)app);
        return 0;
    }
    case WM_PAINT:
        app->on_paint(hwnd);
        return 0;
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}
```

## 3. Message Loop Patterns

### Standard loop (desktop apps)

```cpp
int run_message_loop() {
    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0) > 0) {
        TranslateMessage(&msg);   // Generate WM_CHAR from WM_KEYDOWN
        DispatchMessageW(&msg);
    }
    return (int)msg.wParam;
}
```

### Real-time loop (games, animation)

```cpp
void run_realtime_loop() {
    MSG msg;
    bool running = true;
    while (running) {
        while (PeekMessageW(&msg, NULL, 0, 0, PM_REMOVE)) {
            if (msg.message == WM_QUIT) { running = false; break; }
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
        if (running) {
            update();
            render();
        }
    }
}
```

### Hybrid loop (messages + kernel objects)

```cpp
void run_hybrid_loop(HANDLE hStopEvent) {
    MSG msg;
    bool running = true;
    while (running) {
        DWORD result = MsgWaitForMultipleObjects(
            1, &hStopEvent, FALSE, INFINITE, QS_ALLINPUT);

        if (result == WAIT_OBJECT_0) {
            running = false;
        } else if (result == WAIT_OBJECT_0 + 1) {
            while (PeekMessageW(&msg, NULL, 0, 0, PM_REMOVE)) {
                if (msg.message == WM_QUIT) { running = false; break; }
                TranslateMessage(&msg);
                DispatchMessageW(&msg);
            }
        }
    }
}
```

### Accelerator table (keyboard shortcuts)

```cpp
HACCEL hAccel = LoadAcceleratorsW(hInst, MAKEINTRESOURCEW(IDR_ACCEL));
MSG msg;
while (GetMessageW(&msg, NULL, 0, 0) > 0) {
    if (!TranslateAcceleratorW(hwnd, hAccel, &msg)) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
}
```

## 4. Common Messages

| Message | When | Key Params |
|---------|------|------------|
| `WM_CREATE` | Window created | `lp` → `CREATESTRUCT*` |
| `WM_DESTROY` | Window being destroyed | Call `PostQuitMessage(0)` |
| `WM_CLOSE` | User clicked X | Call `DestroyWindow(hwnd)` or block |
| `WM_PAINT` | Need to repaint | Use `BeginPaint`/`EndPaint` |
| `WM_SIZE` | Window resized | `lp` = LOWORD(w) + HIWORD(h) |
| `WM_COMMAND` | Menu/button/accelerator | LOWORD(wp) = ID |
| `WM_KEYDOWN` | Key pressed | `wp` = virtual key code |
| `WM_CHAR` | Character input | `wp` = Unicode char |
| `WM_MOUSEMOVE` | Mouse moved | `lp` = LOWORD(x) + HIWORD(y) |
| `WM_LBUTTONDOWN` | Left click | `lp` = position |
| `WM_TIMER` | Timer tick | `wp` = timer ID |
| `WM_DPICHANGED` | DPI changed (per-monitor) | `wp` = new DPI, `lp` → `RECT*` |

### Custom messages

```cpp
constexpr UINT WM_APP_TASK_DONE = WM_APP + 1;

// Post from worker thread (async, thread-safe)
PostMessage(hwnd, WM_APP_TASK_DONE, status_code, (LPARAM)result_ptr);

// Never use SendMessage from worker thread — deadlock risk
```

## 5. Window Subclassing

```cpp
WNDPROC g_original_proc = nullptr;

LRESULT CALLBACK SubProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    if (msg == WM_KEYDOWN && wp == VK_ESCAPE) {
        PostMessage(hwnd, WM_CLOSE, 0, 0);
        return 0;
    }
    return CallWindowProcW(g_original_proc, hwnd, msg, wp, lp);
}

// Install
g_original_proc = (WNDPROC)SetWindowLongPtrW(hwnd, GWLP_WNDPROC, (LONG_PTR)SubProc);

// Restore
SetWindowLongPtrW(hwnd, GWLP_WNDPROC, (LONG_PTR)g_original_proc);
```

## 6. GDI Drawing

### WM_PAINT handler

```cpp
case WM_PAINT: {
    PAINTSTRUCT ps;
    HDC hdc = BeginPaint(hwnd, &ps);

    // Draw text
    SetTextColor(hdc, RGB(0, 0, 0));
    SetBkMode(hdc, TRANSPARENT);
    TextOutW(hdc, 10, 10, L"Hello", 5);

    // Draw rectangle
    RECT rc = { 50, 50, 200, 150 };
    FillRect(hdc, &rc, (HBRUSH)(COLOR_HIGHLIGHT + 1));
    FrameRect(hdc, &rc, (HBRUSH)GetStockObject(BLACK_BRUSH));

    // Draw line
    MoveToEx(hdc, 10, 200, NULL);
    LineTo(hdc, 300, 200);

    EndPaint(hwnd, &ps);
    return 0;
}
```

### Double buffering (flicker-free)

```cpp
case WM_PAINT: {
    PAINTSTRUCT ps;
    HDC hdc = BeginPaint(hwnd, &ps);

    RECT rc;
    GetClientRect(hwnd, &rc);
    int w = rc.right, h = rc.bottom;

    // Create off-screen buffer
    HDC memDC = CreateCompatibleDC(hdc);
    HBITMAP memBmp = CreateCompatibleBitmap(hdc, w, h);
    HBITMAP oldBmp = (HBITMAP)SelectObject(memDC, memBmp);

    // Draw to buffer
    FillRect(memDC, &rc, (HBRUSH)(COLOR_WINDOW + 1));
    draw_scene(memDC, w, h);

    // Copy to screen
    BitBlt(hdc, 0, 0, w, h, memDC, 0, 0, SRCCOPY);

    // Cleanup
    SelectObject(memDC, oldBmp);
    DeleteObject(memBmp);
    DeleteDC(memDC);
    EndPaint(hwnd, &ps);
    return 0;
}
```

### Force repaint

```cpp
InvalidateRect(hwnd, NULL, TRUE);  // Entire client area, erase background
InvalidateRect(hwnd, &dirty_rect, FALSE);  // Partial, no erase
```

## 7. DPI Awareness

```cpp
// Call before creating any window (Windows 10 1703+)
SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);

// Scale values by DPI
UINT dpi = GetDpiForWindow(hwnd);
int scaled_px = MulDiv(logical_value, dpi, 96);

// Handle WM_DPICHANGED
case WM_DPICHANGED: {
    UINT new_dpi = HIWORD(wp);
    RECT* suggested = (RECT*)lp;
    SetWindowPos(hwnd, NULL,
        suggested->left, suggested->top,
        suggested->right - suggested->left,
        suggested->bottom - suggested->top,
        SWP_NOZORDER | SWP_NOACTIVATE);
    // Recalculate layout with new_dpi
    return 0;
}
```

## 8. Window Styles & Properties

### Common style flags

```
WS_OVERLAPPEDWINDOW  — Standard app window (title + border + resize + sysmenu)
WS_POPUP             — No title bar or border (splash screens, tooltips)
WS_CHILD             — Child of another window (controls)
WS_VISIBLE           — Initially visible

WS_EX_TOPMOST        — Always on top
WS_EX_LAYERED        — For alpha blending / transparency
WS_EX_TRANSPARENT    — Click-through
WS_EX_TOOLWINDOW     — Excluded from taskbar
WS_EX_NOACTIVATE     — Doesn't steal focus
```

### Layered / transparent window

```cpp
SetWindowLongPtrW(hwnd, GWL_EXSTYLE,
    GetWindowLongPtrW(hwnd, GWL_EXSTYLE) | WS_EX_LAYERED);
SetLayeredWindowAttributes(hwnd, 0, 200, LWA_ALPHA);  // 200/255 opacity

// Per-pixel alpha with UpdateLayeredWindow
UpdateLayeredWindow(hwnd, NULL, &pos, &size, memDC, &srcPos,
                    0, &blend, ULW_ALPHA);
```

### Timer

```cpp
SetTimer(hwnd, TIMER_ID_1, 16 /*ms*/, NULL);  // ~60 FPS

case WM_TIMER:
    if (wp == TIMER_ID_1) {
        update_animation();
        InvalidateRect(hwnd, NULL, FALSE);
    }
    return 0;

// Cleanup
KillTimer(hwnd, TIMER_ID_1);
```
