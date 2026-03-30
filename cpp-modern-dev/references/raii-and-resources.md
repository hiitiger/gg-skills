# RAII & Resource Management

> **Concurrency RAII** (lock guards, jthread): see **cpp-concurrency** skill
> **Platform RAII** (Win32 HANDLE, COM, GPU): see **cpp-win32-systems** skill

## Ownership Analysis

### Who owns this resource?

| Pattern | Meaning | Use For |
|---------|---------|---------|
| Return `unique_ptr<T>` | Caller receives ownership | Factory functions |
| Accept `unique_ptr<T>` by value | Caller gives up ownership | Sink functions |
| Accept `T*` or `T&` | Borrowing, no ownership transfer | Most function params |
| Return `shared_ptr<T>` | Shared ownership | Caches, async callbacks |

### Risk detection

| Risk | Symptom | Fix |
|------|---------|-----|
| **Memory leak** | `new` without matching `delete`; early return skips cleanup | Wrap in `unique_ptr` |
| **Double free** | Two owners both call `delete` | Use `unique_ptr` or `shared_ptr` |
| **Dangling pointer** | Pointer to destroyed object | `weak_ptr::lock()` or redesign lifetime |
| **Use after move** | Access moved-from object | Mark moved-from state, use linters |
| **Exception leak** | `new` then throw before `delete` | RAII wraps before any throwing code |

## Smart Pointer Choice

```
Ownership question:
|- Single owner (99% of cases) -> unique_ptr
|  |- C API resource? -> unique_ptr + custom deleter
|  \- Need more control? -> Full RAII wrapper class
|- True shared ownership (rare) -> shared_ptr
|  |- Object must outlive async callbacks -> shared_ptr + shared_from_this
|  \- Reference cycle possible -> break with weak_ptr
\- Non-owning observer -> weak_ptr (for shared_ptr targets) or raw T*/T&
```

**`shared_ptr` costs:** extra heap allocation for control block, atomic ref counting, larger than raw pointer. Don't use for convenience -- only for true shared ownership.

## Parameter Conventions

```cpp
void use(Widget& w);                              // Required, non-null, borrow
void use(const Widget& w);                        // Read-only borrow
void use(Widget* w);                              // Optional, non-owning (nullable)
void take(std::unique_ptr<Widget> w);             // Takes ownership (sink)
void share(std::shared_ptr<Widget> w);            // Joins ownership

// BAD: NEVER: pass smart pointer by reference to "borrow"
void bad(const std::unique_ptr<Widget>& w);       // Just use Widget& or Widget*
```

## Custom RAII Wrapper Checklist

When `unique_ptr` + custom deleter isn't enough and you need a full wrapper:

- `std::exchange` in move constructor and move-assignment
- Move operations are `noexcept`
- Delete copy constructor and copy-assignment (unless deep copy makes sense)
- Self-assignment check in move-assignment
- `explicit operator bool` -- prevent accidental implicit conversions
- `release()` escape hatch for C API interop

> **Full Rule of Five pattern**: see [core-language.md](core-language.md) # Rule of Five

## Pitfalls

| Pitfall | What Goes Wrong | Fix |
|---------|----------------|-----|
| Exception between `new` and RAII wrap | Leak if next line throws | Wrap in `make_unique` immediately |
| `shared_ptr` cycle (A->B->A) | Ref count never reaches 0, memory leak | Break cycle with `weak_ptr` |
| Returning reference to local | Dangling reference | Return by value (RVO applies) |
| `shared_ptr` as default choice | Unnecessary atomic overhead, unclear ownership | `unique_ptr` unless sharing is required |

## Code Review Questions

1. Every `new` has a matching smart pointer?
2. Every `acquire_*()` call has RAII?
3. Raw pointer in a class member? -> Who owns it?
4. `shared_ptr` used? -> Is shared ownership truly needed?
5. Custom destructor without move ops? -> Rule of Five violation
