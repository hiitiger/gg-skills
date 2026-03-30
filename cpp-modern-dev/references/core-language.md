# Core Language Patterns

## Rule of Zero / Five

### Decision

```
Does your class directly manage a raw resource (raw pointer, file descriptor, C handle)?
|- No -> Rule of Zero: don't write any special member functions
|       Compiler generates correct copy/move/destructor from members
|       unique_ptr members make it move-only automatically -- that's fine
\- Yes -> Rule of Five: write ALL five (destructor, copy ctor, copy assign, move ctor, move assign)
```

### Rule of Five: Key Requirements

- Move operations must be `noexcept` (required for `std::vector` reallocation)
- Use `std::exchange` in move operations to null out the source
- Copy-assignment via copy-and-swap idiom (strong exception safety)
- If only move makes sense, `= delete` the copy operations
- Explicitly `= default` or `= delete` -- don't leave implicit

## Spaceship Operator (C++20)

`auto operator<=>(const T&) const = default;` generates all six comparison operators. Prefer over manual operators or CRTP Comparable.

**Ordering categories** (choose based on semantics):
- `std::strong_ordering` -- equal values are indistinguishable (int, string)
- `std::weak_ordering` -- equivalent but distinguishable (case-insensitive string)
- `std::partial_ordering` -- some values incomparable (float with NaN)

When customizing `<=>`, also default `operator==` separately -- the compiler won't synthesize `==` from a custom `<=>`.

## Inheritance Rules

- `virtual ~Base() = default` on any polymorphic base
- Always `override`, use `final` to prevent further overriding
- Prefer composition over inheritance
- Consider NVI (Non-Virtual Interface): public non-virtual calls private virtual

## Lambda Capture Rules

- `[&]` for short-lived lambdas in local scope only
- Explicit captures for lambdas stored or passed to other threads
- `[x = std::move(obj)]` to move into lambda (init capture)
- `std::function` has overhead -- use templates or `std::move_only_function` (C++23) in hot paths

## Modernization Cheat Sheet

| Legacy | Modern | Standard |
|--------|--------|----------|
| `NULL` | `nullptr` | C++11 |
| `typedef X Y` | `using Y = X` | C++11 |
| `enum { A, B }` | `enum class E { A, B }` | C++11 |
| `new T` / `delete` | `make_unique<T>()` | C++14 |
| `(int)x` | `static_cast<int>(x)` | C++11 |
| `#define CONST 42` | `inline constexpr int CONST = 42` | C++17 |
| `pair.first` | `auto [a, b] = pair` | C++17 |
| `bool` + out-param | `std::optional<T>` | C++17 |
| `const char*` param | `std::string_view` | C++17 |
| Manual `==`/`<`/`>`... | `auto operator<=>(const T&) const = default` | C++20 |
| `T*` + size param | `std::span<T>` | C++20 |
| `enable_if<>` | `concept` / `requires` | C++20 |
| `printf` | `std::format` / `std::print` | C++20/23 |
| `__FILE__`/`__LINE__` | `std::source_location` | C++20 |
| error code `int` | `std::expected<T, E>` | C++23 |
| `std::function` (hot path) | `std::move_only_function` | C++23 |
