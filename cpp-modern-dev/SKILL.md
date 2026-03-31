---
name: cpp-modern-dev
description: Modern C++ design and implementation guidance for C++17/20/23. Use when a task requires non-trivial decisions about ownership and RAII, class or API design, STL or container choice, templates or concepts, type safety (`optional`/`variant`/`expected`/`span`), error-handling strategy, modern CMake, or C++ performance tradeoffs. Prefer more specific skills for concurrency-heavy or platform-specific work.
---

# Modern C++ Development

## How to Use

1. Use the decision tree to pick **one** reference -- read only that file.
2. If the task spans two areas (e.g., RAII + templates), read the second on demand.

## References

| Category | When to Use | Reference |
|----------|------------|-----------|
| **Build & Tooling** | New project, CMake setup, compiler flags | [build-and-tooling.md](references/build-and-tooling.md) |
| **Build Advanced** | Sanitizers, packages, modules, cross-compile | [build-advanced.md](references/build-advanced.md) |
| **RAII & Resources** | Smart pointers, custom RAII wrappers, ownership analysis | [raii-and-resources.md](references/raii-and-resources.md) |
| **Core Language** | Class design, Rule of Zero/Five, spaceship operator, move semantics | [core-language.md](references/core-language.md) |
| **Templates & Generics** | Concepts (C++20), SFINAE, if constexpr, CRTP | [templates-and-generics.md](references/templates-and-generics.md) |
| **STL & Algorithms** | Container choice, ranges (C++20), standard algorithms | [stl-and-algorithms.md](references/stl-and-algorithms.md) |
| **Type Safety** | optional, variant, expected, span, narrowing | [type-safety.md](references/type-safety.md) |
| **Error Handling** | Exceptions vs error codes, expected (C++23), strategy choice | [error-handling.md](references/error-handling.md) |
| **Performance Patterns** | Move semantics, allocation, cache, profiling | [performance-patterns.md](references/performance-patterns.md) |

## Core Rules

1. **Model resource lifetime explicitly** -- prefer scope-bound ownership and RAII wrappers over manual acquire/release.
2. **Rule of Zero by default** -- compose from smart pointers and standard containers. Write special members only when the type directly manages a raw resource; then implement or delete the full set that matches the ownership semantics.
3. **Prefer `unique_ptr` for exclusive ownership** -- use `shared_ptr` only for true shared ownership. For borrowing, pass `T&` or `T*`, not smart pointers by reference.
4. **Use `const`, `noexcept`, `explicit`, and `[[nodiscard]]` to clarify intent** -- mark move operations `noexcept` when possible, single-argument constructors `explicit`, and return values `[[nodiscard]]` when ignoring them is likely a bug.
5. **Default to views for read-only input and values for output when lifetime and ABI constraints allow it** -- `string_view`, `span`, and `const T&` reduce copies; return by value when ownership transfers cleanly. Never return a view to a local.
6. **Profile before optimizing** -- correctness -> clarity -> measure -> optimize the bottleneck -> measure again
7. **Repository conventions win on style** -- follow the existing codebase for naming, include structure, type aliases, `const` placement, and other local conventions.

## Default Standard

Target C++17 as baseline. Use C++20/23 features when the project's CMake target or existing code indicates support.
