# Build & Tooling -- Advanced

> Core build setup -> [build-and-tooling.md](build-and-tooling.md)

## Sanitizers

### CMake integration

```cmake
# Address Sanitizer -- buffer overflow, use-after-free, leaks
target_compile_options(tgt PRIVATE -fsanitize=address -fno-omit-frame-pointer)
target_link_options(tgt PRIVATE -fsanitize=address)

# Undefined Behavior Sanitizer
target_compile_options(tgt PRIVATE -fsanitize=undefined)
target_link_options(tgt PRIVATE -fsanitize=undefined)

# Thread Sanitizer -- data races (cannot combine with ASan)
target_compile_options(tgt PRIVATE -fsanitize=thread)
target_link_options(tgt PRIVATE -fsanitize=thread)
```

**Rule:** ASan + UBSan can combine. TSan and ASan cannot -- use separate build configs.

### Static Analysis

```cmake
# Clang-Tidy
set(CMAKE_CXX_CLANG_TIDY "clang-tidy;-checks=-*,bugprone-*,modernize-*,performance-*")

# Cppcheck
find_program(CPPCHECK cppcheck)
if(CPPCHECK)
    set(CMAKE_CXX_CPPCHECK "${CPPCHECK};--enable=all;--suppress=missingInclude")
endif()
```

## Package Management

**vcpkg** (manifest mode):
```json
// vcpkg.json
{ "name": "myproject", "dependencies": ["fmt", "spdlog", "catch2"] }
```
```cmake
set(CMAKE_TOOLCHAIN_FILE "$ENV{VCPKG_ROOT}/scripts/buildsystems/vcpkg.cmake")
```

**Conan**: `conanfile.txt` with `[requires]` + `CMakeDeps`/`CMakeToolchain` generators.

**FetchContent**: for header-only or small deps. Use `FetchContent_Declare` + `FetchContent_MakeAvailable`.

## Precompiled Headers

```cmake
target_precompile_headers(mylib PRIVATE <vector> <string> <memory> <unordered_map>)
target_precompile_headers(mytest REUSE_FROM mylib)  # Share PCH
```

## C++20 Modules

### Compiler support status

| Compiler | Support | Notes |
|----------|---------|-------|
| MSVC (VS 2022 17.5+) | Best | Named modules, `import std` |
| Clang 16+ | Partial | Requires `-fmodules` |
| GCC 14+ | Experimental | Limited |

**Recommendation:** Use modules for new MSVC-only projects. Keep headers for cross-compiler code until Clang/GCC stabilize.

### CMake support

```cmake
# CMake 3.28+ required
target_sources(mylib PUBLIC FILE_SET CXX_MODULES FILES src/math.cppm)
```

## Cross-Compilation

Use a toolchain file: set `CMAKE_SYSTEM_NAME`, `CMAKE_SYSTEM_PROCESSOR`, `CMAKE_C_COMPILER`, `CMAKE_CXX_COMPILER`, and `CMAKE_FIND_ROOT_PATH_MODE_*` variables. Pass via `-DCMAKE_TOOLCHAIN_FILE=toolchain.cmake`.
