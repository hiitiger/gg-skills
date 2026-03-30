# Build & Tooling

## Table of Contents
1. Target Standards & Feature Detection
2. Project Structure Decision
3. Modern CMake Principles
4. Warning Flags

> Advanced: sanitizers, package mgmt, PCH, modules, cross-compilation -> [build-advanced.md](build-advanced.md)

## 1. Target Standards & Feature Detection

| Standard | Status | Guideline |
|----------|--------|-----------|
| **C++17** | Baseline | Default minimum target |
| **C++20** | Preferred | Use when project supports it (concepts, ranges, span, coroutines) |
| **C++23** | Optional | Use `std::expected`, `std::print`, `std::flat_map` where available |

### Feature-test macros (check before using newer features)

```
__cpp_concepts            (C++20)    __cpp_lib_expected       (C++23)
__cpp_lib_ranges          (C++20)    __cpp_lib_format         (C++20)
__cpp_lib_span            (C++20)    __cpp_lib_optional       (C++17)
__cpp_consteval           (C++20)    __cpp_lib_variant        (C++17)
__cpp_structured_bindings (C++17)    __cpp_if_constexpr       (C++17)
```

## 2. Project Structure Decision

| Criteria | Colocated headers | Separate include/ |
|----------|:-:|:-:|
| Multi-module with internal dependencies | [x] | |
| Single library published for external use | | [x] |
| Header and source always edited together | [x] | |
| Clear public API boundary needed | | [x] |

**Colocated** (recommended for most projects): headers live alongside source in each module. Expose via CMake `target_include_directories(mod PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})`.

**Separate include/** (for published libraries): public headers in `include/project/`, implementation in `src/`. Expose via `target_include_directories(lib PUBLIC include PRIVATE src)`.

**Conventions (both):** `#pragma once`, one class per file, out-of-source builds (`build/` gitignored).

## 3. Modern CMake Principles

### Do

```cmake
# Target-based: properties propagate through target_link_libraries
target_link_libraries(mylib PUBLIC fmt::fmt)
target_compile_definitions(mylib PRIVATE DEBUG_MODE=1)
target_compile_features(mylib PUBLIC cxx_std_20)
```

### Don't

```cmake
# Global: affects everything, breaks encapsulation
add_definitions(-DDEBUG)          # Use target_compile_definitions
include_directories(include)      # Use target_include_directories
link_libraries(fmt)               # Use target_link_libraries
```

### Generator expressions (per-config, per-compiler)

```cmake
target_compile_options(mylib PRIVATE
    $<$<CONFIG:Debug>:-O0 -g>
    $<$<CONFIG:Release>:-O2 -DNDEBUG>
    $<$<CXX_COMPILER_ID:MSVC>:/W4 /WX>
    $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall -Wextra -Wpedantic -Werror>
    $<$<PLATFORM_ID:Windows>:-DWIN32_LEAN_AND_MEAN>
)
```

## 4. Warning Flags

### GCC / Clang

```cmake
target_compile_options(mylib PRIVATE
    -Wall -Wextra -Wpedantic
    -Wshadow -Wconversion -Wsign-conversion
    -Wnon-virtual-dtor -Wold-style-cast
    -Woverloaded-virtual -Wnull-dereference -Wformat=2
)
```

### MSVC

```cmake
target_compile_options(mylib PRIVATE
    /W4 /WX /permissive-
    /w14242 /w14254 /w14263 /w14265
    /w14287 /w14296 /w14311 /w14826 /w14928
)
```

MSVC `/w1XXXX` flags: narrowing (4242), operator conversion (4254), override mismatch (4263), non-virtual dtor (4265), unsigned/negative (4287), always true/false (4296), pointer truncation (4311), signed/unsigned (4826), illegal copy-init (4928).
