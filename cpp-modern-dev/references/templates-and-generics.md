# Templates & Generics

## Choosing the Right Abstraction

```
Need to constrain template parameters?
|- C++20+ -> Concepts (preferred)
|- C++17 -> if constexpr + type traits (simple cases)
|          SFINAE / enable_if (complex overload sets)
\- Both available? -> Always prefer concepts

Need compile-time polymorphism?
|- Inject reusable behavior into unrelated types -> CRTP mixin
|- Eliminate virtual dispatch overhead -> CRTP or concepts
\- Type-safe heterogeneous dispatch -> std::variant + visit

Need compile-time evaluation?
|- Can evaluate at compile time, may also run at runtime -> constexpr
|- Must evaluate at compile time only -> consteval (C++20)
\- Initialize at compile time, mutable at runtime -> constinit (C++20)
```

## Concepts (C++20) -- Preferred Constraint Mechanism

**Standard concepts** (use before writing custom): `std::integral`, `std::floating_point`, `std::convertible_to`, `std::same_as`, `std::ranges::range`, `std::input_or_output_iterator`, `std::invocable`.

**Custom concept pattern:**

```cpp
template <typename T>
concept Hashable = requires(T t) {
    { std::hash<T>{}(t) } -> std::convertible_to<size_t>;
};
```

Four equivalent ways to apply: `template <Hashable T>`, `Hashable auto`, `requires Hashable<T>` clause, or trailing requires.

## CRTP -- When and Why

Static polymorphism with zero overhead. Use for **mixin patterns** that inject behavior into unrelated derived classes (e.g., Printable, Serializable, Comparable).

**Don't use CRTP for:**
- Comparison operators -> `operator<=>` = default (C++20)
- Simple code reuse -> composition or free functions
- Open-ended type sets -> virtual functions

## Type Traits Quick Reference

| Category | Commonly Used |
|----------|--------------|
| Query | `is_integral_v`, `is_floating_point_v`, `is_pointer_v`, `is_same_v<A,B>`, `is_base_of_v<B,D>`, `is_trivially_copyable_v` |
| Transform | `remove_const_t`, `remove_reference_t`, `decay_t`, `conditional_t<B,T,F>`, `common_type_t` |
| Detection | `std::void_t` + partial specialization (C++17), or concepts (C++20) |

## Template Pitfalls

| Pitfall | Fix |
|---------|-----|
| Forgetting deduction guides for class templates (C++17) | Add explicit deduction guide or use factory function |
| Full specialization of function templates | Prefer overloading -- specialization doesn't participate in overload resolution |
| SFINAE error messages are cryptic | Migrate to concepts for clear constraint violation messages |
| Template code in .cpp file -> linker error | Keep in header, or use explicit instantiation |
| `sizeof...(Args)` confused with `sizeof(Args)` | `sizeof...` counts parameter pack, `sizeof` gives byte size |
