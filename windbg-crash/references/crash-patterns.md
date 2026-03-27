# Crash Patterns and Diagnostic Paths

Before using any path below, classify the dump:
- **Minidump**: start with exception record, stack, registers, modules, and thread state.
- **Full dump**: memory, heap, address-space, and locals inspection are usually available.
- If a command fails because memory/heap/pages are unavailable, treat that as a **dump limitation**, not as evidence that the suspected bug pattern is absent.

## 1. Null Pointer Dereference

**Symptoms:** ACCESS_VIOLATION reading/writing address near 0x00000000
**Diagnosis:**
```
.ecxr
kp          # find the faulting frame
r           # check which register holds null
ub <eip>    # disassemble backward to see what set it null
u <eip> L3  # disassemble forward — decode the faulting instruction
dv          # local variables in faulting frame
```
`dv` may be unavailable without private symbols. If so, rely on registers, disassembly, and the calling stack.

**Sub-pattern: null `this` pointer (AV at small offset):**
If the AV address is a small non-zero value (e.g. `0x0000002C`, `0x00000048`), the crash is almost always a member access on a null object pointer:
- The offset = the struct/class member offset being accessed
- Use `dt <module>!<ClassName>` (if symbols available) to find which member lives at that offset
- Check the calling frame to find where the null object pointer originated
- Common causes: `this` passed as null from caller, container returned null iterator, factory returned null

**Sub-pattern: vtable dispatch on null object:**
If the faulting instruction is `call [reg+N]` or `call [reg]` where `reg` is 0:
```
# The crash is a virtual function call on a null object pointer
# reg = vtable pointer, which was read from address 0x0 (the null this pointer)
# N = vtable slot offset → identifies which virtual function was called
# Divide N by pointer size (4 for x86, 8 for x64) to get the vtable slot index
```

**Sub-pattern: null function pointer call:**
If the faulting instruction is at or near address `0x00000000`:
```
# The program called through a null function pointer
# Look at the CALLER frame (one above) to see what variable held the function pointer
ub <return_address_on_stack>  # disassemble the call site
```

**Root cause:** Unchecked return value, race condition, logic error, or uninitialized pointer.

## 2. Use-After-Free (UAF)

**Symptoms:** ACCESS_VIOLATION at address with heap fill patterns (0xFEEEFEEE, 0xDDDDDDDD)
**Diagnosis:**
```
!heap -p -a <address>         # page heap trace (if enabled)
!heap -x <address>            # find heap block containing address
!address <address>            # memory region info
dps <address> L10             # dump pointers — look for vtable remnants
```
`!heap*`, `!address`, and `dps <address>` often need more than a minimal minidump. If they fail, do not rule out UAF; downgrade confidence and ask for full dump or page heap repro.

**Recognizing fill patterns in AV address or memory content:**

| Pattern | Meaning | Source |
|---------|---------|--------|
| `0xFEEEFEEE` | Freed memory | `HeapFree()` fill |
| `0xDDDDDDDD` | Freed memory | Debug CRT `_free_dbg` |
| `0xCDCDCDCD` | Uninitialized heap | Debug CRT `_malloc_dbg` |
| `0xFDFDFDFD` | Guard bytes around heap block | Debug CRT buffer overrun sentinel |
| `0xABABABAB` | Guard bytes after allocated block | Win32 heap |
| `0xBAADF00D` | Uninitialized `LocalAlloc(LMEM_FIXED)` | Win32 heap |

**vtable forensics (identifying the destroyed object's class):**
```
# If dps <address> shows pointer-like values at offset 0 (vtable position):
ln poi(<address>)             # try to resolve vtable pointer to a symbol
# If vtable points to valid code → the object was reused by a different class (type confusion)
# If vtable points to freed/invalid memory → the object was freed but vtable not yet overwritten
# Compare with a known valid vtable:
dps <valid_object_of_same_class> L1   # dump vtable of a live object for comparison
```

**`!heap -x` output interpretation:**
```
# !heap -x <addr> returns the heap block that contains <addr>:
#   Entry     UserPtr   UserSize  Flags
#   <block>   <uptr>    <usize>   <flags>
# Key fields:
#   UserPtr = start of user-allocated memory
#   UserSize = allocation size
#   Flags: if shows "free" or "internal" → block was already freed → confirms UAF
# Calculate offset: <addr> - UserPtr = offset within the original allocation
# This offset can help identify which struct member was being accessed
```

**If page heap not enabled**, recommend user re-run with:
```
gflags /p /enable <exe> /full
```

## 3. Heap Corruption

**Symptoms:** Exception 0xC0000374, or crash inside ntdll!RtlAllocateHeap / ntdll!RtlFreeHeap
**Diagnosis:**
```
!heap -s                      # heap summary
!heap -triage [<heap>|<addr>] # validate a suspect heap or heap block
!heap -p -a <address>         # page heap details
!avrf                         # application verifier (if enabled)
```
On minidumps, heap commands commonly lack enough backing data. If so, keep the diagnosis at "suspected heap corruption" unless the stack and exception record are decisive.
Do not use `!heap -a <handle>` here. `-a` is not the "validate this heap handle" form; for corruption triage prefer `!heap -triage`, and use `!heap -p -a <addr>` when page heap data exists for a specific address.
**Note:** The crash point is often NOT the corruption point. Enable page heap to catch the real culprit.

## 4. Stack Overflow

**Symptoms:** Exception 0xC00000FD, ESP/RSP near guard page
**Diagnosis:**
```
!teb                          # stack base/limit
kp 200                        # long stack trace — look for recursion
!uniqstack                    # deduplicate thread stacks
dps @rsp L2000                # raw stack dump if k fails
```
`dps @rsp` requires readable stack memory. If the dump does not contain it, report that manual reconstruction is unavailable.
**Look for:** Recursive call pattern, deep callback chains, large local arrays.

## 5. C++ Exception (Unhandled)

**Symptoms:** Exception 0xE06D7363
**Diagnosis:**
```
.exr -1                       # exception record
# Param[1] = pointer to _ThrowInfo, Param[2] = pointer to exception object
dt <exception_addr> <type>    # if type known
!sehchain                     # SEH handler chain
!cppexn <exception_record>    # (SOS/MEX) parse C++ exception
```

**Extracting MSVC exception type name (manual method):**

The MSVC C++ exception record contains structured metadata that reveals the thrown type.
Exception parameters layout (from `.exr -1`):
- `NumberParameters: 3` (32-bit) or `4` (64-bit with `__ImageBase`)
- `Param[0]`: magic constant (`0x19930520`)
- `Param[1]`: pointer to the thrown object
- `Param[2]`: pointer to `_ThrowInfo`
- `Param[3]` (x64 only): module `__ImageBase` (used as RVA base)

**x86 (32-bit) type name extraction:**
```
# Given Param[2] = _ThrowInfo address:
dd <Param[2]>+0xC L1                       # → pCatchableTypeArray pointer
dd poi(<Param[2]>+0xC)+0x4 L1              # → first CatchableType pointer
dd poi(poi(<Param[2]>+0xC)+0x4)+0x4 L1     # → TypeDescriptor pointer
da poi(poi(<Param[2]>+0xC)+0x4)+0x4+0x8    # → type name string (mangled)
# Or as one-liner:
da poi(poi(poi(<Param[2]>+0xC)+0x4)+0x4)+0x8
```

**x64 (64-bit) type name extraction:**
On x64, `_ThrowInfo` and sub-structures use RVAs (relative virtual addresses) from the module's `__ImageBase` (Param[3]). All pointer fields must be treated as `ImageBase + RVA`:
```
# Given: Param[2] = _ThrowInfo*, Param[3] = ImageBase
# Step 1: get CatchableTypeArray RVA from _ThrowInfo
dd <Param[2]>+0x10 L1                      # → CatchableTypeArray RVA
# Step 2: compute CatchableTypeArray address = ImageBase + RVA
# Step 3: get first CatchableType RVA
dd <ImageBase>+<ArrayRVA>+0x4 L1           # → first CatchableType RVA
# Step 4: get TypeDescriptor RVA from CatchableType
dd <ImageBase>+<TypeRVA>+0x4 L1            # → TypeDescriptor RVA
# Step 5: read type name (mangled name starts at TypeDescriptor+0x10 on x64)
da <ImageBase>+<DescRVA>+0x10
# The result is a mangled C++ name like ".?AVruntime_error@std@@"
# Decode: remove leading ".?AV" and trailing "@@" → "runtime_error" in namespace "std"
```

**Common thrown types and their meanings:**
- `std::bad_alloc` → allocation failure (OOM)
- `std::runtime_error` / `std::logic_error` → application-level error
- `std::invalid_argument` → bad function argument
- `CMemoryException` (MFC) → MFC out of memory
- `_com_error` → COM HRESULT failure wrapped as exception

## 6. Stack Buffer Overrun (/GS)

**Symptoms:** Exception 0xC0000409, `__report_gsfailure` on stack
**Diagnosis:**
```
kp                            # the frame before __report_gsfailure is the vulnerable function
ub <return_address>           # look at buffer usage in that function
dv                            # local variables
```

## 7. Deadlock (hang dump, not crash)

**Symptoms:** All threads waiting, no exception
**Diagnosis:**
```
!locks                        # critical section info
!cs -l                        # locked critical sections
~*e !clrstack                 # (.NET) all managed stacks
~*kvn                         # all native stacks with frame numbers
!runaway                      # thread CPU time — find who is busy
```

**Wait chain reconstruction:**
1. Identify waiting threads: look for `WaitForSingleObject`, `WaitForMultipleObjects`, `EnterCriticalSection`, `RtlAcquireSRWLockExclusive`, `NtWaitForAlertByThreadId` in thread stacks
2. For each waiting thread, find what resource it's waiting on:
   - `!cs <addr>` — shows owning thread ID for critical sections
   - `!handle <h> f` — shows handle type and details
3. Trace the chain: Thread A waits for lock X → lock X is held by Thread B → Thread B waits for lock Y → ... → deadlock if chain forms a cycle

**SRWLock analysis (no built-in `!cs` equivalent):**
SRWLocks are lightweight and don't have an owner field like critical sections. Diagnosis approach:
```
~*kvn                         # find all threads in RtlAcquireSRWLock*
# Look for the SRWLock address in the first argument (rcx on x64, stack on x86)
# Then find which thread holds it by looking for code paths that acquired the same lock address
# Cross-reference with threads that are NOT waiting — one of them likely holds the lock
```

**Common deadlock patterns:**
- **Lock ordering violation**: Thread A holds L1, waits L2; Thread B holds L2, waits L1
- **UI thread blocked**: main thread waiting for worker → worker sends `SendMessage` → needs UI thread → deadlock
- **COM STA marshaling**: cross-apartment COM call to STA that is blocked
- **Loader lock**: `DllMain` calls function that waits for another thread to finish its `DllMain`

## 8. Stack Unwinding Failures

**Symptoms:** `k` shows garbage, missing frames, or only 1-2 frames
**Possible causes:**
- Missing/wrong symbols
- FPO (frame pointer omission) without correct PDB
- Stack corruption
- Inline functions

**Manual stack reconstruction:**
```
.ecxr                         # restore exception context first
.kframes 100                  # increase max frames
kp                            # retry
# If still broken:
!teb                          # get stack base and limit
dps @rsp <stack_base>         # dump raw stack with symbol resolution
# Look for return addresses — functions matching known module patterns
# Use ub <address> to verify each candidate is a real return address
ln <address>                  # find nearest symbol
.frame /r <n>                 # switch to a specific frame and check registers
```

**With .frame trick for partial reconstruction:**
```
# If you find a valid return address at rsp+offset:
r rsp = @rsp + <offset>      # adjust stack pointer (CAUTION: modifies context)
k                             # retry stack walk from new position
```

## 9. Pure Virtual Function Call

**Symptoms:** `_purecall` or `R6025` on stack
**Diagnosis:**
```
kp                            # find the caller of __purecall
# The frame before __purecall called a virtual function on a partially constructed/destroyed object
dps <this_ptr>                # dump vtable — should show __purecall entries
ln poi(<this_ptr>)            # identify which class vtable this is
```

## 10. CRT Abort / assert

**Symptoms:** `abort()`, `_wassert`, `_invalid_parameter` on stack
**Diagnosis:**
```
kp                            # stack shows the assert/abort origin
da/du <message_ptr>           # read the assertion message string if available
```

## 11. Out of Memory (OOM)

**Symptoms:** `TerminateBecauseOutOfMemory`, `OnNoMemoryInternal`, `RaiseException` with custom code (e.g. `0xE0000008`), or `0xC0000017` (STATUS_NO_MEMORY). Exception Parameter[0] often contains the failed allocation size.

**Diagnosis (requires full dump):**
```
!address -summary             # VA space overview — check Free %, largest free block
~                             # thread count (each thread stack consumes ~1MB VA)
!heap -s                      # heap summary
!heap -stat -h 0              # default heap statistics
!handle -summary              # handle count by type — check for handle leaks
```
If `!address -summary` or `!heap -s` cannot inspect the target, you cannot confirm or exclude VA exhaustion from that dump alone.

**Distinguishing VA exhaustion vs commit limit exhaustion:**
- **VA exhaustion** (32-bit only): `!address -summary` shows little Free space, but system physical memory may be fine. The process ran out of virtual address space.
- **Commit limit** exhaustion: affects all processes. The system's total committed memory (RAM + pagefile) is full. Check `!address -summary` → `Committed` bytes vs system commit limit.
- **Allocation failure size matters**: if Parameter[0] shows a huge allocation (>1GB), the code may have a size calculation bug (integer overflow → requesting absurd size).

**Key indicators:**
- Total Free VA < 200 MB on 32-bit process → address space pressure
- Largest free region < requested allocation size → fragmentation is the killer
- High thread count (100+) → each thread stack reserves ~1MB contiguous VA

**Checking for Handle / Thread leaks as OOM contributors:**
```
~                             # thread count — hundreds of threads = leak suspect
!handle -summary              # total handle count and breakdown by type
# Normal process: < 1000 handles, < 50 threads
# Suspected leak: > 5000 handles or > 200 threads
!heap -stat -h <handle>       # per-heap stats — look for one heap with most allocations
!heap -flt s <size>           # find all blocks of a suspect size (e.g. same-size small blocks = leak)
```

**Heap fragmentation analysis:**
```
!address -summary             # compare "Free" total vs "Largest Free" region
# If Free total >> Largest Free → severe fragmentation
# Example: Free = 500MB but LargestFree = 2MB → cannot satisfy a 10MB allocation
!heap -stat -h 0              # look at block size distribution
# Many small free blocks between busy blocks = fragmented heap
```

**32-bit VA space exhaustion (most common OOM pattern):**
- 32-bit processes have 2 GB VA limit (4 GB with `/LARGEADDRESSAWARE`)
- Heavy frameworks (CEF/Chromium, .NET, Java) can consume 1+ GB of images alone
- Memory-mapped files and DLLs further fragment the address space
- Even with "free" memory remaining, no single contiguous block may be large enough

**Recommendations by severity:**
1. Migrate to 64-bit (eliminates the problem)
2. Set `/LARGEADDRESSAWARE` linker flag (doubles VA from 2GB to 4GB on 64-bit OS)
3. Reduce thread stack size (`CreateThread` with smaller `dwStackSize`)
4. Reduce DLL count / delay-load non-critical modules
5. Audit memory-mapped file usage

## 12. CRT Invalid Parameter

**Symptoms:** `_invalid_parameter`, `_invalid_parameter_noinfo` on stack, custom exception from invalid parameter handler
**Diagnosis:**
```
.ecxr
kp                            # find the CRT function that detected the invalid parameter
# Common culprits: printf-family with NULL format, fclose on invalid FILE*
# Look at the frame ABOVE _invalid_parameter for the actual bad call
.frame <N>                    # switch to the calling frame
dv                            # inspect local variables — look for NULL pointers
```
If `dv` is unavailable, use the caller frame, argument registers/stack slots, and CRT helper names as weaker evidence rather than forcing a definitive conclusion.

## 13. DEP Violation / Execute Access Violation

**Symptoms:** ACCESS_VIOLATION with `Param[0] = 8`, faulting address in heap/stack/data page, or jump/call into non-image memory
**Diagnosis:**
```
.ecxr
.exr -1
kp
r
!address <fault_addr>            # inspect page type and protection
u <fault_addr> L10               # disassemble around target if readable
ln <fault_addr>                  # see whether address belongs to a known module
ub <return_address>              # find who transferred control there
```

**Interpretation:**
- If `!address` shows `PAGE_READWRITE` / heap / stack memory, code attempted to execute non-executable data
- If the address resolves to freed memory or a heap block, suspect corrupted function pointer, overwritten return address, or UAF
- If the target is near shellcode-like bytes or random data, suspect memory corruption before the actual crash

**Common causes:**
- Corrupted callback / vtable / function pointer
- Return address overwrite from stack corruption
- Jump into JIT buffer or trampoline whose protection was never changed to executable

## 14. Illegal Instruction / Bad Function Pointer

**Symptoms:** Exception `0xC000001D`, faulting instruction decodes as garbage, or control lands in data bytes instead of real code
**Diagnosis:**
```
.ecxr
kp
r
u <eip_or_rip> L10               # decode the illegal instruction stream
!address <eip_or_rip>            # find what kind of memory contains the bytes
ln <eip_or_rip>                  # nearest symbol, if any
ub <eip_or_rip>                  # inspect preceding control flow
```

**Interpretation checklist:**
- If disassembly is nonsense and memory is heap/stack/data -> bad function pointer or corrupted return address
- If memory belongs to a valid module but bytes are unexpected -> code overwrite, wrong module version, or bad patch/hook
- If instruction is a newer CPU opcode on older hardware -> unsupported instruction set (rare in desktop crash dumps, but real)

**Typical root causes:**
- Calling through an overwritten function pointer
- Vtable corruption / type confusion
- Code page corruption
- Mismatched binary and PDB leading to misleading symbols; verify with `lm vm <module>`

## 15. Call Into Unloaded Module

**Symptoms:** Stack shows return/call target in module that is no longer loaded, `WARNING: Frame IP not in any known module`, or address falls in freed image range
**Diagnosis:**
```
.ecxr
kp
lm
ln <fault_addr>
!address <fault_addr>
dps @rsp L40                     # or dps @esp L40 on x86
```

**What to look for:**
- `ln <fault_addr>` fails to resolve to a loaded module, but the address is near where a DLL used to live
- `!address <fault_addr>` shows `MEM_FREE`, `MEM_RESERVE`, or private memory instead of `MEM_IMAGE`
- Stack contains callbacks/timers/threadpool work items that outlived DLL unload

**Typical scenarios:**
- Plugin DLL unloaded while async callback still references its code
- COM object/server unloaded while interface pointer is still in use
- Threadpool timer, APC, window proc, hook proc, or posted task fires after module teardown

**Recommended follow-up:**
- Check teardown paths for `FreeLibrary`, module refcount ownership, and callback cancellation
- If possible, inspect module lifetime around the crashing thread's work item origin

## 16. Double Free / Invalid Free

**Symptoms:** Crash in `RtlFreeHeap`, `HeapFree`, debug CRT free helpers, or heap corruption shortly after a free path
**Diagnosis:**
```
.ecxr
kp
!heap -x <addr>
!heap -p -a <addr>
!heap -triage <addr>
```

If the faulting address is not obvious, start from the block/parameter passed to the free routine in the calling frame.

**Evidence patterns:**
- `!heap -x` shows the block is already free
- Page heap reports a prior free stack for the same block
- Crash happens on a second owner path that frees memory after transfer of ownership

**Common root causes:**
- Two owners both call `delete` / `free`
- Error cleanup path frees object already released on success path
- Refcount races causing final release to run twice

**Important note:**
Without page heap or full heap metadata, many dumps can only support a diagnosis of "suspected double free / invalid free." Prefer page heap repro for confirmation.

## 17. COM / RPC Failure Crash

**Symptoms:** Crash around `combase`, `ole32`, proxy/stub code, marshaling helpers, or interface method call on invalid pointer
**Diagnosis:**
```
.ecxr
kp
r
!peb
dps <this_ptr> L4                # inspect COM object vtable / interface pointer
ln poi(<this_ptr>)               # identify interface vtable owner if readable
!error <hresult_or_ntstatus>     # decode HRESULT/NTSTATUS if present
```

**Sub-patterns:**
- **Invalid interface pointer**: `this` points to freed memory or invalid vtable -> UAF on COM object
- **Cross-apartment / STA block**: stacks show COM marshaling (`ObjectStubless`, `Ndr*`, `CCliModalLoop`) and caller waits on blocked STA thread
- **Bad HRESULT escalation**: app converts failed COM call into fail-fast/assert/crash

**What to check:**
- Whether the interface pointer's vtable belongs to the expected module
- Whether the caller is on the correct apartment/thread model
- Whether object lifetime crossed async boundary without `AddRef` / ownership handoff

## 18. Handle Leak / GDI Resource Exhaustion

**Symptoms:** OOM-like behavior, UI failures, inability to create windows/bitmaps/fonts, or crashes after resource allocation APIs fail
**Diagnosis:**
```
!handle -summary                # handle counts by type
!handle 0 0                     # enumerate handles if dump supports it
kp
!gle                            # last Win32 error on current thread
```

If this is a GUI process and extensions are available, also try:
```
!gdiobj
```

**Interpretation:**
- Rapidly growing handle counts of one type (event, file, section, thread, reg key) -> leak in ownership/close path
- UI/resource allocation failures with high GDI object count -> bitmap/font/pen/brush leak
- High thread handle count often pairs with thread leak and worsens VA pressure in 32-bit processes

**Typical next steps:**
- Correlate failing API from stack with resource type from `!handle -summary`
- Audit missing `CloseHandle`, `DeleteObject`, `Release`, or RAII ownership boundaries
- For repeated same-type allocations, inspect caller frames above the creation API for leak origin

## 19. vtable-Based Object Search (Finding `this` Pointers)

When you know the class type but need to find live or dangling object instances in memory:

**Technique:**
```
# Step 1: Find the vtable address for the class
x Module!ClassName::*vftable*         # → vtable_address

# Step 2: Search memory for pointers to that vtable
s -d <search_start> L<search_length> <vtable_address>
# Each hit is a potential object instance (vtable pointer at offset 0)
```

**When to use:**
- UAF investigation — find other instances of the same class to compare with the corrupted one
- Identifying which object was involved when `this` is null or corrupted but the class is known from the stack
- Counting live instances to detect leaks of a specific object type

**Caveats:**
- Only works with polymorphic classes (classes with virtual functions)
- Requires symbols for the module that defines the class
- Inherited classes share base vtable prefix but have their own vtable — search results may include derived classes
- On minidumps, memory search range is limited to captured pages

## 20. Inline Hook / Code Patching

**Symptoms:** Crash at or near a function entry point, illegal instruction, or unexpected `jmp`/`call` at function start

**Diagnosis:**
```
.ecxr
u <faulting_address> L10              # disassemble — look for jmp/call at function entry
ub <faulting_address>                 # check preceding bytes
!address <faulting_address>           # verify memory is MEM_IMAGE
ln <faulting_address>                 # identify the function
lm vm <module>                        # check module version / integrity
```

**Signs of hooking:**
- Function starts with `jmp <addr>` or `push <addr>; ret` instead of normal prologue (`push ebp; mov ebp, esp` or `sub rsp`)
- First 5-15 bytes replaced with a detour, rest of function is intact
- The jump target is in a different module or in allocated private memory (not MEM_IMAGE)

**Common causes:**
- Third-party software (antivirus, overlay, input method) hooking system or application functions
- Game anti-cheat or DRM injecting detours
- Malware / adware hooks
- Application's own hot-patching mechanism with a bug

**Follow-up:**
- Identify the hook target module: `ln <jump_target>` or `!address <jump_target>`
- Compare function bytes with known-good binary if available
- Check for common hooking frameworks (Detours, MinHook) in module list

## 21. Reentrant Crash

**Symptoms:** Same function appears multiple times in the call stack (recursive or reentrant call through message dispatch, callbacks, or exception handling)

**Diagnosis:**
```
.ecxr
kp 200                                # look for repeated function patterns
dds @esp L200                         # (x86) scan raw stack for return addresses
dps @rsp L200                         # (x64) scan raw stack for return addresses
```

**What to look for:**
- The same function appearing at multiple stack depths (direct recursion)
- A message pump (`DispatchMessage`, `PeekMessage`) or COM dispatch in the middle of a call chain that re-enters the same code
- Exception handler or `__finally` block that calls back into the faulting code path
- Timer/callback firing during a blocking call in the same function

**Common scenarios:**
- `SendMessage` from within a window procedure handler → re-enters the same WndProc
- COM call triggers message dispatch → re-enters the calling code
- Exception filter/handler calls a function that throws again
- Reentrancy into non-reentrant code corrupts shared state (member variables, globals)

## 22. Optimized Code Analysis Caveats

This is not a crash pattern but an important trust/reliability note for analyzing release builds.

**Parameter unreliability:**
- In optimized builds, the compiler may reuse stack slots allocated for function parameters to store local temporaries
- `kp` parameter values may show stale or unrelated data, not the original arguments
- Leaf functions or inlined functions may not have a stack frame at all

**Mitigation:**
```
kf                                    # check frame sizes — zero-size frames may be inlined
.frame /r <N>                         # switch to frame and check register state
ub <return_address>                   # disassemble call site to see what was actually passed
```

**OMAP / PGO / COMDAT folding effects:**
- Profile-guided optimization (PGO) may reorder code blocks — `ub` may show unrelated code if blocks are non-contiguous
- COMDAT folding merges identical functions — `ln` may resolve to the wrong function name
- When in doubt, verify with `uf <addr>` to see the full function body rather than trusting `ln` alone

**Rule of thumb:** In optimized builds, trust registers and disassembly over `kp` parameters and `dv` locals.

## 23. CRT Version Mismatch

**Symptoms:** Crash in CRT functions (`free`, `delete`, `fclose`, etc.) where the object was allocated by a different CRT instance

**Diagnosis:**
```
lm                                    # look for multiple CRT DLLs (e.g. msvcr120 + msvcr140)
lm vm msvcr*                          # version details of all loaded CRT modules
lm vm vcruntime*
lm vm ucrtbase*
kp                                    # the free/delete call — which CRT module is it in?
# Check the allocating path: was the object created by a different module using a different CRT?
```

**How it happens:**
- Application links against CRT version A, a plugin/DLL links against CRT version B
- Object allocated with CRT-A's `malloc`, freed with CRT-B's `free` → heap corruption or crash
- Installing a new VC++ redistributable at runtime can cause newly loaded DLLs to pick up a different CRT version than existing DLLs

**Key indicators:**
- Multiple `msvcr*.dll` or `vcruntime*.dll` in the module list with different version numbers
- Crash in `free`/`delete` where the calling module and the allocating module use different CRTs
- Heap corruption patterns that only occur with specific plugin/DLL combinations

**Prevention:**
- Use a single CRT version across all modules (static or dynamic linking, but consistent)
- Export allocation/deallocation as pairs from the same module
- Use COM-style `Release()` or module-specific `Free()` functions instead of cross-module `delete`
