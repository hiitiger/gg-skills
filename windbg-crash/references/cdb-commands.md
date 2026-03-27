# cdb/WinDbg Command Reference by Scenario

## Initial Context

| Command | Purpose |
|---------|---------|
| `\|\|` | Dump file type and path |
| `\|` | Process info (PID, name) |
| `.time` | System time, process uptime, dump creation time |
| `!peb` | Process environment block (command line, env vars, CWD) |
| `vertarget` | Target OS version, machine type |

## Exception & Crash Context

| Command | Purpose |
|---------|---------|
| `.exr -1` | Last exception record (code, address, params) |
| `.ecxr` | Set context to exception record (MUST run before `k` for crash context) |
| `!analyze -v` | Automatic crash analysis with faulting module/function |
| `.lastevent` | Show the last debug event / exception stop reason |
| `!error <code>` | Look up NTSTATUS/Win32 error code |
| `!gle` | Show current thread's last Win32 error / last NTSTATUS |

## Stack Traces

| Command | Purpose |
|---------|---------|
| `k` | Basic stack trace |
| `kp` | Stack with function parameters |
| `kn` | Stack with frame numbers |
| `kvn` | Stack with frame numbers and FPO info |
| `kf` | Stack with frame sizes (helps find large locals) |
| `kv=<ebp> <esp>` | Stack walk with manually specified base/stack pointers (x86) |
| `~*k` | All thread stacks |
| `~*kvn` | All thread stacks with frame numbers |
| `!uniqstack` | Unique stacks (deduplicated across threads) |
| `.kframes <N>` | Set max stack depth (default 20, try 100+) |

## Registers & Local Variables

| Command | Purpose |
|---------|---------|
| `r` | All registers |
| `r <reg>` | Single register value |
| `dv` | Local variables (requires private symbols) |
| `dv /t /V` | Local vars with type and address |
| `.frame <N>` | Switch to frame N |
| `.frame /r <N>` | Switch to frame N and show registers |

## Memory Inspection

| Command | Purpose |
|---------|---------|
| `dd <addr>` | Dump DWORDs |
| `dq <addr>` | Dump QWORDs |
| `da <addr>` | Dump ASCII string |
| `du <addr>` | Dump Unicode string |
| `dps <addr> [L<count>]` | Dump pointers with symbol resolution |
| `dds <addr>` | Dump DWORDs with symbol resolution |
| `dpa <addr>` | Dereference pointer and display as ASCII string |
| `dpu <addr>` | Dereference pointer and display as Unicode string |
| `dpp <addr>` | Double-dereference pointer (pointer to pointer) |
| `dl <addr>` | Walk and display a linked list (LIST_ENTRY) |
| `!address <addr>` | Memory region info (type, protection, state) |
| `!vprot <addr>` | Virtual protection flags |
| `!vadump` | Dump the virtual address descriptor / VA layout details |
| `s -a <start> L<len> "pattern"` | Search memory for ASCII pattern |
| `s -d <start> L<len> <value>` | Search memory for DWORD value |

## Disassembly

| Command | Purpose |
|---------|---------|
| `u <addr>` | Disassemble forward from address |
| `ub <addr>` | Disassemble backward (useful for seeing code before crash) |
| `uf <func>` | Disassemble full function |
| `u <addr> L<N>` | Disassemble N instructions |
| `.fnent <addr>` | Show function entry / unwind metadata for an address |

## Heap Analysis

| Command | Purpose |
|---------|---------|
| `!heap -s` | Summary of all heaps |
| `!heap -a` | Expand heap details / enumerate heap contents (not a heap-handle validator) |
| `!heap -triage [<handle>|<addr>]` | Validate a suspect heap or heap block in corruption scenarios |
| `!heap -x <addr>` | Find heap block containing address |
| `!heap -p -a <addr>` | Page heap details for address (requires gflags) |
| `!heap -i <addr>` | Heap block info for a specific address |
| `!heap -flt s <size>` | Filter heap blocks by size |
| `!heap -stat -h <handle>` | Heap statistics |

## Modules

| Command | Purpose |
|---------|---------|
| `lm` | List all loaded modules |
| `lm vm <module>` | Verbose info for specific module (version, path, symbols) |
| `!lmi <module>` | Module details |
| `!dh <module>` | Inspect PE headers / sections / image characteristics |
| `ln <addr>` | Find nearest symbol to address |
| `.reload /f` | Force reload all symbols |
| `.reload /f <module>` | Force reload specific module symbols |
| `.reload /u <module>` | Unload module symbols (prep for re-mapping) |
| `.reload /f /i <pdb>=<addr>` | Force load PDB at specific base address (for unloaded modules) |
| `!sym noisy` | Enable verbose symbol loading diagnostics |

## Thread Management

| Command | Purpose |
|---------|---------|
| `~` | List all threads |
| `~<N>s` | Switch to thread N |
| `~<N>k` | Stack of thread N |
| `~*k` | Stacks of all threads |
| `!runaway` | Thread CPU time (find busy/stuck threads) |
| `!teb` | Thread environment block (stack base, limit) |

## Synchronization / Lock Analysis

| Command | Purpose |
|---------|---------|
| `!locks` | Display all locked critical sections |
| `!cs -l` | All currently held critical sections |
| `!cs <addr>` | Details of a specific critical section |
| `!handle` | Handle table summary |
| `!handle <h> f` | Details of specific handle |

## Symbols

| Command | Purpose |
|---------|---------|
| `.sympath` | Show current symbol path |
| `.sympath+ <path>` | Append to symbol path |
| `.symfix` | Set to Microsoft public symbol server |
| `!sym noisy` | Verbose symbol loading |
| `!sym quiet` | Quiet symbol loading |
| `x <module>!<pattern>` | Search for symbols (wildcard supported) |

## Data Type Inspection

| Command | Purpose |
|---------|---------|
| `dt <type>` | Display type layout |
| `dt <type> <addr>` | Display typed data at address |
| `dt -r <type> <addr>` | Recursive type dump (expand nested structs) |
| `?? sizeof(<type>)` | Size of a type |

## Useful Expressions

| Command | Purpose |
|---------|---------|
| `? <expr>` | Evaluate MASM expression |
| `?? <expr>` | Evaluate C++ expression |
| `.formats <value>` | Show a value in hex/decimal/binary/time/float-friendly formats |
| `poi(<addr>)` | Dereference pointer at address |
