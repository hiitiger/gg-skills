# Type Safety Patterns

## When to Use Which

| Scenario | Type | Standard |
|----------|------|----------|
| Might not have a value (lookup miss) | `std::optional<T>` | C++17 |
| One of several known types | `std::variant<Ts...>` | C++17 |
| Value or error | `std::expected<T, E>` | C++23 |
| Open-ended type (rare) | `std::any` | C++17 |

**Key rules:**
- `optional`: replaces `T*` or `pair<T, bool>` for "maybe" semantics. **Not** for error handling -- use `expected`.
- `variant`: no heap alloc, type-safe. Prefer over `any` when types are known. Prefer over inheritance for closed type sets.
- `expected`: for expected failures (parse, I/O). No unwinding cost. Prefer over exceptions in performance-sensitive paths.
- `any`: only for truly open type sets (plugin systems). Almost always wrong -- prefer `variant`.
- **Never** `optional<T&>` -- use `T*` for optional references.

## Overloaded Visitor Pattern

The standard way to dispatch on variant alternatives. Prefer over `holds_alternative` + `get`:

```cpp
template <class... Ts> struct overloaded : Ts... { using Ts::operator()...; };
template <class... Ts> overloaded(Ts...) -> overloaded<Ts...>;

std::visit(overloaded{
    [](int i)    { /* ... */ },
    [](double d) { /* ... */ },
    [](const std::string& s) { /* ... */ },
}, my_variant);
```

## Variant as State Machine

Variant naturally models state machines -- each state is a struct, transitions return new states:

```cpp
struct Disconnected {};
struct Connecting { std::string host; };
struct Connected { int socket_fd; };
struct Error { std::string message; };

using State = std::variant<Disconnected, Connecting, Connected, Error>;

State on_connect(State state, const std::string& host) {
    return std::visit(overloaded{
        [&](Disconnected) -> State { return Connecting{host}; },
        [&](auto&) -> State { return state; },
    }, state);
}
```

## View Type Rules

| Rule | Why |
|------|-----|
| Use `string_view`/`span` for read-only params | Accepts any compatible source without copy |
| **Never** return `string_view` to a local string | Dangling -- the local is destroyed |
| **Never** store as member unless lifetime guaranteed | The viewed data may be freed |
| `string_view::substr()` is free | No allocation -- just adjusts pointer + length |
| `span<T, N>` for fixed-size views | Compile-time size check |

## Strong Type Aliases

Prevent unit/type confusion at compile time when multiple parameters share the same underlying type:

```cpp
struct Width { int value; };
struct Height { int value; };
void set_rect(Width w, Height h);  // Can't accidentally swap width/height
```

For a generic version, use a tag-based `StrongType<T, Tag>` wrapper.

## Monadic Operations (C++23)

Available on both `optional` and `expected`:

```cpp
find_user(id)
    .transform([](User& u) { return u.name; })
    .or_else([] { return std::optional<std::string>("guest"); });
```

Operations: `.transform()` (map value), `.and_then()` (flat-map value), `.or_else()` (handle empty/error).
