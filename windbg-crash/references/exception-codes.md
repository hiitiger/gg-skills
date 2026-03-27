# Common Windows Exception Codes

| Code | Name | Typical Cause |
|------|------|---------------|
| `0xC0000005` | ACCESS_VIOLATION | Null/wild pointer dereference, use-after-free, buffer overrun |
| `0xC00000FD` | STACK_OVERFLOW | Infinite recursion, large stack allocation |
| `0xC0000008` | INVALID_HANDLE | Using closed/invalid handle |
| `0xC0000017` | NO_MEMORY | Heap exhaustion, memory leak |
| `0xC0000135` | UNABLE_TO_LOCATE_DLL | Missing dependent DLL, bad deployment, search path issue |
| `0xC0000142` | DLL_INIT_FAILED | `DllMain` initialization failure, loader-lock bug, dependency init failure |
| `0xC0000374` | HEAP_CORRUPTION | Heap buffer overrun, double free, write-after-free |
| `0xC0000409` | STACK_BUFFER_OVERRUN | /GS security cookie check failed |
| `0xC0000420` | ASSERTION_FAILURE | Explicit assertion / diagnostic fast-fail style abort |
| `0xC0000194` | POSSIBLE_DEADLOCK | Application Verifier / runtime deadlock detection |
| `0xC000001D` | ILLEGAL_INSTRUCTION | Bad function pointer, corrupted code |
| `0xC0000094` | INTEGER_DIVIDE_BY_ZERO | Division by zero |
| `0xC0000096` | PRIVILEGED_INSTRUCTION | Executing kernel-only instruction in user mode |
| `0xC00002B4` | FLOAT_MULTIPLE_FAULTS | FPU exception |
| `0xE06D7363` | C++ Exception (`msc`) | Unhandled C++ throw (`std::exception` and derived) |
| `0xE0434352` | CLR Exception (`.COM`) | .NET unhandled exception |
| `0x40010006` | CTRL_C_EXIT | Process terminated via Ctrl+C |
| `0x406D1388` | MSVC Thread Naming | Debugger-only thread naming exception; usually benign |
| `0xC0000602` | FAIL_FAST | `__fastfail()` called — deliberate abort |
| `0x80000003` | BREAKPOINT | `int 3` / `DebugBreak()` / `__debugbreak()` |
| `0x80000004` | SINGLE_STEP | Hardware single-step trap |
| `0xCFFFFFFF` | Application-defined | Custom `RaiseException` — check first param |

## Common Custom/Application Exception Codes

| Code | Origin | Meaning |
|------|--------|---------|
| `0xE0000008` | Chromium/CEF PartitionAlloc | Out of memory — `TerminateBecauseOutOfMemory` |
| `0xE0000001`-`0xEFFFFFFF` | Application-defined range | Custom `RaiseException` — check `Parameter[0]` for allocation size or error detail |

When encountering unknown exception codes in the `0xE0xxxxxx` range, check the stack for OOM handlers (`OnNoMemoryInternal`, `TerminateBecauseOutOfMemory`) or CRT handlers (`_invalid_parameter`, `_purecall`).

## Notes on Less-Obvious Codes

- `0x406D1388` is commonly raised by MSVC thread-naming helpers for the debugger. Do not treat it as a crash unless it is actually unhandled in production logic.
- `0xC0000135` usually means process startup or delayed-load failure. Inspect loader-related stacks, `!peb`, module load paths, and deployment packaging.
- `0xC0000142` often points at work done inside `DllMain`, dependency initialization failure, or loader-lock-sensitive code paths.
- `0xC0000194` frequently appears with verifier/instrumentation enabled; treat it as a strong deadlock signal and inspect lock ownership across threads.
- `0xC0000420` usually indicates an intentional assertion-style abort. The key task is to find the assertion site and message rather than treating it as random corruption.

## ACCESS_VIOLATION Sub-types

The exception record contains two parameters:
- Param[0]: operation type
  - `0` = read from inaccessible address
  - `1` = write to inaccessible address
  - `8` = DEP violation (execute non-executable memory)
- Param[1]: target address

**Quick patterns:**
- Address near `0x00000000` → null pointer dereference
- Address near a small offset (e.g., `0x0000002C`) → null pointer + struct member offset
- Address `0xCDCDCDCD` → uninitialized heap memory (debug CRT)
- Address `0xDDDDDDDD` → freed heap memory (debug CRT)
- Address `0xFDFDFDFD` → heap guard bytes overrun (debug CRT)
- Address `0xFEEEFEEE` → freed memory (HeapFree fill)
- Address `0xABABABAB` → heap guard after allocated block
- Address `0xBAADF00D` → LocalAlloc(LMEM_FIXED) not yet initialized
