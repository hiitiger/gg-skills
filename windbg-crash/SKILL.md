---
name: windbg-crash
description: "Automated Windows crash dump (.dmp) analysis using cdb.exe/WinDbg. Runs triage commands, identifies crash root cause, and performs deep analysis including manual stack reconstruction. Use when: (1) user provides a .dmp file to analyze, (2) user asks to debug a crash, access violation, or 'why did my program crash', (3) user mentions WinDbg/cdb/crash dump/minidump/full dump/postmortem debugging, (4) user needs to diagnose exception codes in a crash dump context."
---

# WinDbg Crash Dump Analysis

Automated user-mode crash dump analysis via direct cdb.exe invocation. No dependencies beyond the Windows SDK Debugging Tools.

## Invocation Pattern

All cdb commands follow this pattern:

```
"<CDB>" -z "<DUMP>" -y '<SYMBOLS>' -logo NUL -c "<COMMANDS>; q" 2>&1
```

- `<CDB>` -- path to cdb.exe (resolved in Phase 0)
- `<DUMP>` -- path to the .dmp file
- `<SYMBOLS>` -- symbol path in **single quotes** (preserves UNC backslashes like `\\server\share`)
- `-logo NUL` -- suppresses the cdb startup banner
- `2>&1` -- merges stderr into stdout so all output is captured
- Always end commands with `q` to exit cdb

If `_NT_SYMBOL_PATH` is already set in the environment, the `-y` flag can be omitted -- cdb reads the env var automatically.

**Allow 300-600 seconds** for cdb calls -- `!analyze -v` may trigger symbol downloads on first run.

**MINIMIZE CDB LAUNCHES.** Each launch reloads the dump and resolves symbols. Batch all commands for an analysis round into ONE call with semicolons. Multiple rounds are fine; one-command-per-round is not.

## Phase 0: Resolve Prerequisites

Before running any commands, resolve in this order:

### 1. Dump file path
If user did not provide a dump path, ask for it. Verify the file exists.

### 2. cdb.exe path
Default: `C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe`. Verify it exists; only ask if missing.

### 3. Symbol path
Resolve using this priority:
1. **User explicitly provided** -- use it directly (skip confirmation)
2. **Environment variable** -- check if `_NT_SYMBOL_PATH` is set (e.g. `$env:_NT_SYMBOL_PATH` in PowerShell)
3. **Neither available** -- ask the user to provide one

**For case 2: show the detected value and ask: *"detected symbol path: `<value>`, use this or provide a different one?"*** Do NOT proceed without confirmation.

## Phase 1: Triage

Run the initial triage (fast commands first, slow `!analyze -v` last):

```
"<CDB>" -z "<DUMP>" -y '<SYMBOLS>' -logo NUL -c "!sym quiet; ||; |; .time; vertarget; .exr -1; .ecxr; r; lm; .kframes 100; kp; !analyze -v; q" 2>&1
```

Parse the output and identify:
1. **Exception code** -- see [references/exception-codes.md](references/exception-codes.md)
2. **Faulting module and function**
3. **Call stack quality** -- are symbols resolved? Does the stack look reasonable?
4. **`!analyze -v` verdict** -- note the FAULTING_IP, EXCEPTION_RECORD, DEFAULT_BUCKET_ID
5. **Dump type** -- minidump vs full dump (determines available follow-up commands)
6. **Architecture** -- x86 (32-bit) vs x64 (watch for 32-bit VA space exhaustion)
7. **WoW64 detection** -- if `wow64.dll` appears in the module list or `vertarget` shows an effective machine mismatch, the dump is a 32-bit process on 64-bit OS. Flag this for Phase 2.
8. **Runtime context** -- OS version, command line, loader state

**Capability gate** -- before planning deep analysis, classify what the dump can support:
- **Stack and registers available?** Usually yes for crash minidumps and full dumps.
- **Faulting memory readable?** Needed for `dps`, `dd`, `dq`, `da`, `du`, vtable inspection, and raw stack scanning.
- **Heap metadata available?** Needed for `!heap`, `!heap -x`, `!heap -p -a`, and serious UAF/corruption work.
- **Address-space map available?** Needed for `!address` and `!address -summary`.
- **Private symbols available?** Needed for meaningful `dv`, type-aware inspection, and many frame-local conclusions.

Rules:
- **Full dump**: usually all of the above are available; always include `!address -summary` (VA usage, fragmentation, essential for OOM). Still treat command failures as evidence of missing data.
- **Minidump**: default to **stack/register-first analysis**. Only treat heap, address-space, and memory-inspection commands as reliable after you confirm they actually return useful data.
- If a command reports memory unavailable, pages not present, or heap data missing, record that as a **dump limitation**, not as a negative finding. A failed deep command does **not** disprove UAF, corruption, OOM, or bad arguments -- it may only mean the dump is too small.
- If the root cause depends on data the dump cannot provide, explicitly say so and recommend a **full dump** or a repro with **page heap / verifier**.

## Phase 2: Deep Analysis

**Plan ALL follow-up work from the triage output and execute in ONE cdb call.** This single batch covers stack validation, crash-type-specific diagnostics, cross-thread correlation, and module version checks. Decide what to include:

1. **Stack validation** -- stack traces are not always accurate. Signs of a bad stack: very large offsets (`module+0x12345`), sudden jumps between unrelated modules, very few frames, `WARNING: Frame IP not in any known module`. If bad, add `!teb; dps @esp L200` or `dps @rsp L200` for manual reconstruction. See [references/crash-patterns.md](references/crash-patterns.md) section 8. **Optimized code caveat:** in release builds, `kp` parameter values may be unreliable -- trust registers and disassembly over `kp` parameters. See section 22.
2. **WoW64** -- if detected in Phase 1, add `.effmach x86` as the first command. Without this, `kp`, `r`, `dps @esp`, and frame inspection will show the 64-bit WoW64 thunk layer instead of the real 32-bit crash state.
3. **Crash-type-specific commands** -- consult [references/crash-patterns.md](references/crash-patterns.md), match the exception code to the numbered pattern.
4. **Memory/string addresses** -- add `da`, `dd`, `dps` for addresses seen in the triage output.
5. **Runtime / loader context** -- add `!peb; .lastevent` if needed (`vertarget` and `lm` are already in triage).
6. **Cross-thread correlation** -- add `~*kvn`, `!runaway`, `!locks`, `!cs -l` when the crashing thread alone does not explain the crash. Look for lock ownership, object teardown on another thread, or starvation patterns.
7. **Module version / image metadata** -- add `lm vm <module>`, `!lmi <module>`, `!dh <module>` when version mismatch, hooks, or deployment issues are suspected. Especially important for `0xC0000135`/`0xC0000142`, illegal instructions, plugin crashes, and CRT version mismatches (section 23).

```
"<CDB>" -z "<DUMP>" -y '<SYMBOLS>' -logo NUL -c ".ecxr; !teb; dps @esp L200; da <addr1>; dd <addr2> L10; ~*kvn; !runaway; lm vm <module>; q" 2>&1
```

**Try to predict as much as possible** from the triage output. If results reveal new questions, additional cdb calls are expected -- just batch each round's commands into ONE call. Use the capability gate from Phase 1 to decide which command families are safe.

**For 32-bit (x86) processes**, check if the ~2GB VA limit is the bottleneck. Key signs: Free < 200 MB total, largest free region much smaller than the failed allocation, high thread count (100+ threads x 1MB stack = 100MB of VA).

**Recovering symbols for unloaded modules** (Pattern 15):
```
.reload /u <module>                           # unload stale symbol mapping
.reload /f /i <path\to\module.dll>=<baseaddr> # force load symbols at the original base address
```
After reloading, `ln <fault_addr>` and `kp` may resolve previously unknown frames.

## Phase 3: Root Cause Report

Produce a concise report with these sections:
1. **Crash summary** -- exception type, faulting module!function+offset
2. **Root cause** -- what triggered the crash (null ptr, UAF, corruption, OOM, etc.)
3. **Evidence** -- key stack frames, register values, memory state
4. **Confidence** -- high/medium/low based on symbol quality, stack reliability, and dump completeness
5. **Dump limitations** -- what evidence was unavailable because the dump lacked memory, heap, address-space, or private symbols
6. **Recommendations** -- fix suggestions, or further diagnostics if inconclusive (e.g. enable page heap, reproduce with full dump)

**Example:**
```
Crash summary: ACCESS_VIOLATION (read 0x00000028) in MyApp!CObject::GetName+0x1a
Root cause: Null this pointer -- member access at offset 0x28 on null object
Evidence: RCX=0x0000000000000000, faulting instruction mov rax,[rcx+28h],
  caller MyApp!ProcessItem+0x4f passed null return from GetActiveObject()
Confidence: High -- clear null deref with matching register state and disassembly
Dump limitations: Minidump -- heap and address-space commands unavailable
Recommendations: Add null check on GetActiveObject() return in ProcessItem()
```

## Iterative Analysis

Do NOT stop at Phase 1. After each phase, evaluate whether the root cause is clear. If not, run additional cdb calls -- just batch each round's commands together.

**Batch discipline:** Collect ALL needed commands for the current round first, then run them in ONE cdb call. Multiple rounds are fine; one-command-per-round is not. Stop as soon as root cause is clear.

## References

- [references/crash-patterns.md](references/crash-patterns.md) -- crash-type-specific diagnostic paths (23 patterns)
- [references/exception-codes.md](references/exception-codes.md) -- common Windows exception codes
- [references/cdb-commands.md](references/cdb-commands.md) -- cdb command reference by scenario
