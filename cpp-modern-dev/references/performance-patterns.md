# Performance Patterns

> **Related (don't duplicate):**
> - View types (string_view, span) -> [type-safety.md](type-safety.md)
> - Compile-time computation (constexpr) -> [templates-and-generics.md](templates-and-generics.md)
> - Compiler optimization flags -> [build-and-tooling.md](build-and-tooling.md)
> - Container selection -> [stl-and-algorithms.md](stl-and-algorithms.md)

## Table of Contents

1. [Cost Model](#cost-model)
2. [Copy & Move Costs](#copy--move-costs)
3. [Small Object Optimization Thresholds](#small-object-optimization-thresholds)
4. [Parameter Passing Decision](#parameter-passing-decision)
5. [Cache-Friendly Design](#cache-friendly-design)
6. [Virtual Dispatch vs Templates](#virtual-dispatch-vs-templates)
7. [Performance Review Checklist](#performance-review-checklist)

## Cost Model

Profile first, optimize second. But know the orders of magnitude:

```
Operation                          Approx. cost (ns)
-----------------------------------------------------
L1 cache hit                       ~1
L2 cache hit                       ~5
L3 cache hit                       ~15
DRAM access (cache miss)           ~100
Branch misprediction               ~15-20
Virtual function call              ~5-15 (+ potential cache miss)
System call                        ~500-1000
Heap allocation (malloc)           ~50-200
std::mutex lock (uncontended)      ~25
std::atomic (relaxed)              ~1-5
Disk I/O                           ~10,000-10,000,000
Network round trip                 ~500,000+
```

## Copy & Move Costs

| Type | Copy Cost | Move Cost |
|------|-----------|-----------|
| `int`, `float`, `pointer` | Trivial (register) | Same as copy |
| `std::string` (short <=~22 chars) | Trivial (SSO) | Trivial |
| `std::string` (long) | **Heap alloc + memcpy** | Pointer swap |
| `std::vector<T>` | **Heap alloc + N copies** | 3 pointer swaps |
| `std::map<K,V>` | **N node allocations** | Pointer swap |
| `std::array<T,N>` | N copies (stack) | N moves (stack) |
| `std::shared_ptr<T>` | Atomic ref count increment | Pointer swap |
| `std::unique_ptr<T>` | Deleted | Pointer swap |

## Small Object Optimization Thresholds

| Type | SSO/SBO Threshold | Implication |
|------|-------------------|-------------|
| `std::string` | ~15-22 bytes | Short strings: free to copy |
| `std::function` | ~16-32 bytes | Small lambdas stored inline |
| `std::any` | ~16-32 bytes | Small objects stored inline |
| `std::variant` | Size of largest alt | Always inline (no heap) |
| `std::optional` | Size of T | Always inline (no heap) |

## Parameter Passing Decision

```
Is the parameter an input?
|- Small/trivial (int, float, pointer)? -> by value
|- Read-only access? -> const T& (or string_view/span for strings/arrays)
\- Function will store a copy?
   |- Always stores -> T by value, then std::move into member
   \- Sometimes stores -> const T& + copy when needed

Output? -> return by value (RVO applies)
```

**Never `std::move` a local return value** -- it prevents NRVO. Just `return local;`.

### NRVO Pitfall

Returning different named locals from different branches blocks NRVO:
```cpp
// BAD: NRVO blocked
if (flag) return a; else return b;

// [x] Single local, NRVO applies
Widget w;
if (flag) w.configure_a(); else w.configure_b();
return w;
```

## Cache-Friendly Design

### AoS vs SoA

When iterating only 1-2 fields of a large struct across many elements, **Struct of Arrays** gives better cache utilization:

```cpp
// SoA: updating all x-positions hits sequential cache lines
struct Particles {
    std::vector<float> x, y, z, vx, vy, vz;
};
for (size_t i = 0; i < n; ++i) p.x[i] += p.vx[i] * dt;
```

### False Sharing

Adjacent atomics on the same cache line cause contention between threads:
```cpp
struct alignas(64) AlignedCounter { std::atomic<uint64_t> value; };
```

### Hot/Cold Split

Separate frequently-accessed fields from rarely-accessed ones into different containers to avoid cache pollution.

## Virtual Dispatch vs Templates

```
Is the set of types known at compile time?
|- Yes, small set -> std::variant + visit (cache-friendly)
|- Yes, single type -> template (fully inlined)
\- No, open-ended -> virtual (runtime polymorphism)

Is this a hot loop?
|- Yes -> template or variant
\- No -> virtual is fine
```

## Performance Review Checklist

### Allocation
- `new`/`make_unique` in per-frame/per-request loop? -> Reuse buffer, pool, or stack-allocate
- `std::string` constructed just to pass to function? -> Accept `string_view`
- `push_back` without `reserve()` when size is known? -> `reserve()` first

### Copying
- Large value passed by value to read-only function? -> `const T&` or view
- Object copied into member when it could be moved? -> By value + `std::move`

### Data Layout
- `std::list`/`std::map` where `vector` + sort works? -> Profile and switch
- Only 1-2 fields accessed in tight loop over large struct vector? -> Consider SoA
- Per-thread atomics adjacent in memory? -> `alignas(64)`

### Dispatch
- Virtual call in tight loop with known types? -> Template or `variant` + `visit`
- `std::function` in hot path? -> Template param or `move_only_function` (C++23)
