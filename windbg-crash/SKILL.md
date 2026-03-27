---
name: windbg-crash
description: "Automated Windows crash dump (.dmp) analysis using cdb.exe/WinDbg. Runs triage commands, identifies crash root cause, and performs deep analysis including manual stack reconstruction. Use when: (1) user provides a .dmp file to analyze, (2) user asks to debug a crash or access violation, (3) user mentions WinDbg/cdb/crash dump/minidump/full dump analysis, (4) user asks about exception codes or crash patterns."
---

# WinDbg Crash Dump Analysis

Automated user-mode crash dump analysis via cdb.exe. Supports minidump and full dump files, but the available evidence depends heavily on what the dump actually captured.

## Phase 0: Resolve Prerequisites

Before running any commands, resolve the analysis prerequisites in this order:

### 1. Dump file path
If user did not provide a dump path, ask for it. Verify the file exists.

### 2. Symbol path
Resolve symbol path using this priority:
1. **User explicitly provided** in the current message → use it directly (skip confirmation)
2. **Existing `_symbols.txt`** in skill directory → read the file content
3. **Environment variable** → run `scripts/check_symbols.py` to read `_NT_SYMBOL_PATH`
4. **Neither available** → ask the user to provide one

**For cases 2 and 3: ALWAYS show the detected value to the user and ask: *"detected symbol path: `<value>`, use this or provide a different one?"*** Do NOT proceed without confirmation — the user may want to point to a different symbol server or cache for this specific dump.

Once resolved, write the symbol path to a temp file (e.g. `_symbols.txt` next to the skill directory) to avoid shell escaping issues with UNC paths. All subsequent scripts use `--symbols-file`.

### 3. cdb.exe path
Default: `C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe`. Only ask if the default doesn't exist.

### Symbol Path Shell Escaping

**UNC paths (`\\server\share`) lose backslashes when passed through bash/shell arguments.** Always use one of:
- `--symbols-file <file>` — read from a text file (recommended)
- Write a temp Python script with `r"..."` raw strings to bypass shell entirely

Never pass UNC symbol paths via `--symbols` command line in bash.

## Analysis Workflow

**MINIMIZE CDB LAUNCHES.** Each cdb launch has significant overhead (loading dump, resolving symbols). Always batch multiple commands into ONE `run_cdb_cmd.py` call with semicolons. Iterative analysis (multiple rounds) is expected — but each round should be ONE call with ALL commands for that round, not one call per command.

### Phase 1: Initial Triage

Write the resolved symbol path to a file, then run the triage script:

```python
# Write symbol path to file (preserves UNC backslashes)
with open("_symbols.txt", "w") as f:
    f.write(r"<symbol_path>")
```
```bash
# CDB launch #1: triage
PYTHONIOENCODING=utf-8 python scripts/crash_triage.py "<dump_path>" --symbols-file _symbols.txt
```

This executes (in order — fast commands first, slow `!analyze -v` last):
1. `!sym quiet`, `||`, `|`, `.time`, `vertarget`, `.exr -1` — fast, no symbol download
2. `.ecxr`, `r`, `lm` — fast, basic context
3. `.kframes 100`, `kp` — may trigger symbol download for stack modules
4. `!analyze -v` — slowest, triggers full symbol resolution

**Note:** Always set `PYTHONIOENCODING=utf-8` when calling scripts — dump paths with CJK characters or cdb output with replacement characters will cause GBK encoding errors on Chinese Windows.

Parse the output and identify:
1. **Exception code** — see [references/exception-codes.md](references/exception-codes.md)
2. **Faulting module and function**
3. **Call stack quality** — are symbols resolved? Does the stack look reasonable?
4. **`!analyze -v` verdict** — note the FAULTING_IP, EXCEPTION_RECORD, DEFAULT_BUCKET_ID
5. **Dump type** — minidump vs full dump (determines available follow-up commands)
6. **Architecture** — x86 (32-bit) vs x64 (watch for 32-bit VA space exhaustion)
7. **WoW64 detection** — if `wow64.dll` appears in the module list or `vertarget` shows an effective machine mismatch, the dump is a 32-bit process on 64-bit OS. All follow-up commands MUST be preceded by `.effmach x86` to switch to the correct 32-bit context — without this, `kp`, `r`, `dps @esp`, and frame inspection will show the 64-bit WoW64 thunk layer instead of the real crash state.
8. **Runtime context** — OS version, command line, loader state, and last event if `!peb` / `.lastevent` were collected

### Phase 1.5: Capability Gate

Before any "deep" command, classify what the dump can actually support.

Treat these as separate questions:
- **Stack and registers available?** Usually yes for crash minidumps and full dumps.
- **Faulting memory readable?** Needed for `dps`, `dd`, `dq`, `da`, `du`, vtable inspection, and raw stack scanning.
- **Heap metadata available?** Needed for `!heap`, `!heap -x`, `!heap -p -a`, and serious UAF/corruption work.
- **Address-space map available?** Needed for `!address` and `!address -summary`.
- **Private symbols available?** Needed for meaningful `dv`, type-aware inspection, and many frame-local conclusions.

Use this rule set:
- If the dump is a **full dump**, you can usually attempt all of the above, but still treat command failures as evidence of missing data or extension limits.
- If the dump is a **minidump**, default to **stack/register-first analysis**. Only treat heap, address-space, and memory-inspection commands as reliable after you confirm they actually return useful data.
- If a command reports memory unavailable, pages not present, heap data missing, or similar errors, record that as a **dump limitation**, not as a negative finding.

Command families by default safety:

| Usually safe on minidump | Often unavailable on minidump / verify first |
|--------------------------|----------------------------------------------|
| `.exr -1`, `.ecxr`, `kp`, `kn`, `kvn`, `r`, `.time`, `|`, `||`, `lm`, `ln <addr>` | `!address`, `!address -summary`, `!heap*`, `dps <addr>`, `dd/dq/da/du <addr>`, `dv`, `dt <type> <addr>` |

Escalation rule:
- If the root cause depends on heap state, address-space layout, raw memory, or locals and the current dump cannot provide it, explicitly say the current dump is insufficient and recommend a **full dump** or a repro with **page heap / verifier** as appropriate.

### Phase 2: Stack Validation

**CRITICAL:** Stack traces are NOT always accurate. Verify before concluding.

Signs of a bad stack:
- Frames showing only module names without function offsets (`module+0x12345` with very large offsets)
- Sudden jumps between unrelated modules
- Very few frames (1-3) when a deeper stack is expected
- `ntdll!KiUserExceptionDispatcher` at top but no meaningful frames below
- Frames from freed/unloaded modules
- `WARNING: Frame IP not in any known module` followed by garbage addresses

**If stack looks wrong**, attempt manual reconstruction — combine with Phase 3 commands in a single batch (see below).

Only trust this path if the dump actually contains readable stack memory. If `dps @rsp` fails or returns mostly unreadable memory, report "manual stack reconstruction blocked by dump limitations" and do not infer from missing frames alone.

Then analyze the raw `dps` output — look for return addresses matching known module ranges. Use `ln <addr>` and `ub <addr>` to verify candidates. See [references/crash-patterns.md](references/crash-patterns.md) section 8 for detailed guidance.

**Optimized code caveat:** In release builds, `kp` parameter values may be unreliable — the compiler can reuse parameter stack slots for temporaries. Trust registers and disassembly over `kp` parameters and `dv` locals. Use `ub <return_address>` to verify what was actually passed at the call site. See [references/crash-patterns.md](references/crash-patterns.md) section 22 for details.

### Phase 2+3: Combined Deep Analysis

**After triage, plan ALL follow-up work and execute in ONE `run_cdb_cmd.py` call (CDB launch #2).** Do not run Phase 2 and Phase 3 as separate steps — that wastes a CDB launch. Decide from the triage output:
1. Does the stack need reconstruction? (bad stack signs → add `!teb; dps @esp L200` or `dps @rsp L200`)
2. Is this a WoW64 dump? (add `.effmach x86` as the first command)
3. What crash-type-specific commands are needed? (see table below)
4. What memory/string addresses need inspection? (add `da`, `dd`, `dps` for relevant addresses)
5. Do you need runtime / loader context? (add `!peb; .lastevent` — `vertarget` and `lm` are already in triage)
6. Do you need other threads / lock owners? (add `~*kvn`, `!runaway`, `!locks`, `!cs -l`)
7. Do you need exact module version / image metadata? (add `lm vm <module>`, `!lmi <module>`, `!dh <module>`)

**Combine ALL commands into ONE call:**

```bash
# CDB launch #2: all follow-up in one shot
PYTHONIOENCODING=utf-8 python scripts/run_cdb_cmd.py "<dump>" ".ecxr; !teb; dps @esp L200; da <addr1>; dd <addr2> L10; ~*kvn; !runaway; lm vm <module>" --symbols-file _symbols.txt
```

**This is your primary follow-up CDB launch.** Try to predict as much as possible from the triage output and batch it. But if the results reveal new questions (unexpected addresses, suspicious threads, etc.), additional `run_cdb_cmd.py` calls are expected — just batch each round's commands into ONE call rather than running them one by one.

Consult [references/crash-patterns.md](references/crash-patterns.md) for crash-type-specific diagnostic paths.

Pick follow-up commands based on dump capability, not just exception type:
- **Minidump baseline**: focus on exception record, registers, faulting instruction, module list, stack quality, and cross-thread stacks.
- **Full dump**: add heap, address-space, raw memory, vtable, and locals inspection.
- **Unknown / partial dump**: probe one command from a capability family first. If it fails due to missing data, stop using that family and mark the evidence as unavailable.

| Exception | Key follow-up commands |
|-----------|----------------------|
| ACCESS_VIOLATION (0xC0000005) | `!address <addr>`, `!heap -x <addr>`, `!heap -p -a <addr>` |
| STACK_OVERFLOW (0xC00000FD) | `!teb`, `kp 200`, `!uniqstack` |
| HEAP_CORRUPTION (0xC0000374) | `!heap -s`, `!heap -triage [<handle>|<addr>]`, `!heap -p -a <addr>` |
| C++ Exception (0xE06D7363) | `.exr -1`, `!sehchain`, inspect exception object |
| STACK_BUFFER_OVERRUN (0xC0000409) | `kp` (find frame before `__report_gsfailure`) |
| OOM / No Memory | `!address -summary`, `~` (thread count), `!heap -s` |
| CRT Invalid Parameter | `.frame` to calling frame, `dv` to inspect args |
| Deadlock (hang dump) | `!locks`, `!cs -l`, `!runaway`, `~*kvn` |
| Loader / DLL init issues | `vertarget`, `!peb`, `.lastevent`, `lm`, `lm vm <module>` |
| ILLEGAL_INSTRUCTION (0xC000001D) | `u <rip> L10`, `!address <rip>`, `ln <rip>`, check for inline hooks |
| Call into unloaded module | `ln <addr>`, `!address <addr>`, `.reload /u` + `.reload /f /i <dll>=<base>` |

Interpret the table carefully:
- Commands in the table are **candidates**, not guarantees.
- For minidumps, prefer stack-based conclusions first. Use heap/address commands only if they return real data.
- A failed deep command does **not** disprove UAF, corruption, OOM, or bad arguments. It may only mean the dump is too small.

**For full dumps**, always run `!address -summary` — it reveals VA space usage, fragmentation, and is essential for OOM analysis.

**For 32-bit (x86) processes**, check if the ~2GB VA limit is the bottleneck. Key signs:
- Free < 200 MB total
- Largest free region much smaller than the failed allocation
- High thread count (100+ threads x 1MB stack = 100MB of VA)

### Phase 3.5: Cross-Thread Correlation

When the current thread alone does not explain the crash, explicitly correlate with other threads:
- Run `~*kvn` to group threads into waiting, running, worker-pool, UI, COM/RPC, and GC/helper patterns
- Run `!runaway` to identify the hottest thread or a thread spinning while others wait
- For deadlock / hang / callback-lifetime issues, identify resource ownership and cross-thread dependencies rather than only describing the crashing thread
- For module-unload, COM, timer, and async callback cases, look for the thread that created, released, or is still servicing the relevant object/module

Cross-thread questions to answer:
1. Is another thread holding the lock / resource this thread needs?
2. Is another thread tearing down the object / DLL / COM apartment involved in the crash?
3. Is there a busy thread causing starvation while the crashing thread is timing out or failing?

If cross-thread evidence is weak because the dump lacks enough stacks or symbols, record that as a limitation instead of assuming no relationship exists.

### Phase 3.6: Module Version and Image Validation

When a crash may depend on binary version mismatch, patching, hooks, or deployment state:
- Use `lm vm <module>` to capture image path, timestamp, version, and symbol status
- Use `!lmi <module>` for detailed module metadata
- Use `!dh <module>` when you need PE header / section / image characteristic details
- Compare the crashing module version with known-good builds, rollout cohorts, or dependency compatibility requirements

This is especially important for:
- `0xC0000135` / `0xC0000142`
- Illegal instruction / bad code bytes
- Crashes in plugin ecosystems or side-by-side deployment
- Cases where symbols load but may correspond to a different build than the binary in the dump
- Multiple CRT versions loaded (`msvcr*.dll` / `vcruntime*.dll` with different versions) — see [references/crash-patterns.md](references/crash-patterns.md) section 23

**Recovering symbols for unloaded modules:**
When the crash involves a call into an unloaded module (Pattern 15) and you know the module's base address and have access to its PDB or DLL:
```
.reload /u <module>                           # unload stale symbol mapping
.reload /f /i <path\to\module.dll>=<baseaddr> # force load symbols at the original base address
```
After reloading, `ln <fault_addr>` and `kp` may resolve previously unknown frames. The base address can often be found from `lm` output (if the module was captured before unload) or from stack-based evidence.

Run follow-up commands as part of the Phase 2+3 batch — include them in the same `run_cdb_cmd.py` call:
```bash
PYTHONIOENCODING=utf-8 python scripts/run_cdb_cmd.py "<dump>" ".ecxr; lm vm <module>; !lmi <module>; !dh <module>; <other follow-up commands>" --symbols-file _symbols.txt
```

### Phase 4: Root Cause Report

Produce a concise report:
1. **Crash summary** — exception type, faulting module!function+offset
2. **Root cause** — what triggered the crash (null ptr, UAF, corruption, OOM, etc.)
3. **Evidence** — key stack frames, register values, memory state
4. **Confidence** — high/medium/low based on symbol quality, stack reliability, and dump completeness
5. **Dump limitations** — what evidence was unavailable because the dump lacked memory, heap, address-space, or private symbols
6. **Recommendations** — fix suggestions, or further diagnostics if inconclusive (e.g. enable page heap, reproduce with full dump)

## Iterative Analysis

Do NOT stop at Phase 1. After each phase, evaluate whether the root cause is clear. If not:
- Run additional targeted commands via `run_cdb_cmd.py`
- Inspect specific memory addresses, vtables, or data structures
- Check other threads for related activity
- Cross-reference module versions with known bugs
- Re-check whether the dump actually contains the data required by the next command family

**Batch discipline:** When you need more data, collect ALL needed commands for the current round first, then run them in ONE `run_cdb_cmd.py` call. Avoid running individual commands in separate calls — batch per analysis round. Multiple rounds are fine; one-command-per-round is not.

**CDB launch budget:** Each analysis round = 1 `run_cdb_cmd.py` call. Batch all commands for that round together. Stop as soon as root cause is clear.

## Command Reference

For the full cdb command reference organized by scenario, see [references/cdb-commands.md](references/cdb-commands.md).
