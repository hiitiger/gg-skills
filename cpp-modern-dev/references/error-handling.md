# Error Handling Patterns

## Strategy Selection

| Context | Recommended Approach |
|---------|---------------------|
| Truly exceptional / unrecoverable | Exceptions (`throw`) |
| Expected failure (file not found, parse error) | `std::expected` (C++23) or error codes |
| "Maybe no value" (lookup miss) | `std::optional` |
| Programming errors / invariants | `assert` / `static_assert` |
| Library boundary / C interop | Error codes (no exceptions across ABI) |
| Performance-critical hot path | Error codes or `std::expected` |

**Rules:**
- Don't use exceptions for control flow
- Don't use error codes where exceptions are natural (constructors, operators)
- Be consistent within a codebase
- `std::expected` bridges the gap -- value semantics, no unwinding cost, monadic chaining

## Exception Safety Guarantees

| Guarantee | Promise | How to Achieve |
|-----------|---------|----------------|
| **No-throw** | Never throws | Destructors, swap, move ops. Mark `noexcept` |
| **Strong** | On exception: state unchanged | Copy-and-swap idiom, prepare-then-commit |
| **Basic** | Valid but unspecified state. No leaks | RAII ensures this automatically |
| **None** | May leak or corrupt | Bug -- fix it |

**RAII gives you basic guarantee for free.** To upgrade to strong: do all work that might throw on a copy, then swap (noexcept) to commit.

## noexcept Rules

- Move constructors and move-assignment: **always `noexcept`** (required for `std::vector` reallocation optimization)
- Destructors: implicitly `noexcept` -- never throw from destructors
- Swap functions: should be `noexcept`
- Use conditional `noexcept(noexcept(expr))` for generic wrappers

## std::error_code -- When Crossing Boundaries

Use `std::error_code` / `std::error_category` for system-compatible errors across library boundaries. Define a custom `error_category` and register your enum with `is_error_code_enum`.

## Assertions

- `assert(expr)` -- runtime, debug only (removed by `NDEBUG`)
- `static_assert(expr)` -- compile-time, zero runtime cost
- `std::source_location::current()` (C++20) -- modern replacement for `__FILE__`/`__LINE__` in custom assert/log functions. Pass as default parameter to capture caller location.

## Pitfalls

| Pitfall | Fix |
|---------|-----|
| Catching by value (slices derived exceptions) | Always `catch (const E&)` |
| Throwing in destructor | Never. Use `noexcept` (implicit) and handle errors before destruction |
| Error code ignored silently | Use `[[nodiscard]]` on functions returning error codes/expected |
| `assert` in release builds | `assert` is removed by NDEBUG. For release checks, write a custom `verify()` |
