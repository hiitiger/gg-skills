#!/usr/bin/env python3
"""
Crash dump triage script - runs initial diagnostic commands via cdb.exe
with streaming output and step-by-step progress.

Usage:
  python crash_triage.py <dump_path> [--symbols <path>] [--symbols-file <file>]
  python crash_triage.py <dump_path>   (reads _NT_SYMBOL_PATH env var)

Symbol path resolution order:
  1. --symbols-file <file>  (read symbol path from a text file, avoids shell escaping)
  2. --symbols <path>       (direct command line)
  3. _NT_SYMBOL_PATH env var

Output is streamed line-by-line. Each triage command is run separately
with a [STEP N/M] progress label so partial results appear immediately.
Fast commands run first; the slow !analyze -v runs last.
"""
import argparse
import os
import sys
import subprocess
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdb_common import (
    find_cdb, resolve_symbols, filter_noise,
    TRIAGE_FAST, TRIAGE_DEEP, TRIAGE_COMMANDS, add_common_args,
)

ECHO_SENTINEL = "__TRIAGE_STEP_DONE__"


def _drain_stderr(proc, stop_event):
    """Drain stderr in background to prevent blocking."""
    while not stop_event.is_set():
        line = proc.stderr.readline()
        if not line:
            break
        filtered = filter_noise(line)
        if filtered.strip():
            print(f"[cdb stderr] {filtered.strip()}", file=sys.stderr, flush=True)


def _wait_for_prompt(proc):
    """Consume CDB's initial banner until the debugger prompt."""
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        stripped = line.strip()
        if stripped.endswith(">") and ":" in stripped:
            break


def _run_step(proc, cmd):
    """Send one command, stream its output, return True on success."""
    try:
        proc.stdin.write(f"{cmd}; .echo {ECHO_SENTINEL}\n")
        proc.stdin.flush()
    except (BrokenPipeError, OSError):
        return False

    while True:
        try:
            line = proc.stdout.readline()
        except (BrokenPipeError, OSError):
            return False
        if not line:
            return False
        if ECHO_SENTINEL in line:
            break
        filtered = filter_noise(line)
        if filtered:
            print(filtered, end="", flush=True)

    # Consume prompt after sentinel
    try:
        proc.stdout.readline()
    except (BrokenPipeError, OSError):
        pass
    return True


def main():
    parser = argparse.ArgumentParser(description="Crash dump triage via cdb.exe")
    add_common_args(parser)
    parser.add_argument("--commands", "-c", default=None,
                        help="Custom semicolon-separated commands (overrides defaults)")
    args = parser.parse_args()

    if not os.path.isfile(args.dump):
        print(f"[ERROR] Dump file not found: {args.dump}", file=sys.stderr)
        sys.exit(1)

    cdb = find_cdb(args.cdb)
    if not cdb:
        print("[ERROR] cdb.exe not found. Provide --cdb path or install Windows Debugging Tools.", file=sys.stderr)
        sys.exit(1)

    symbols = resolve_symbols(args.symbols, args.symbols_file)

    print(f"[INFO] cdb: {cdb}", flush=True)
    print(f"[INFO] dump: {args.dump}", flush=True)
    print(f"[INFO] symbols: {symbols or '(not set)'}", flush=True)
    print(f"[INFO] timeout: {args.timeout}s", flush=True)

    # Custom commands → fall back to simple one-shot execution
    if args.commands:
        from cdb_common import run_cdb_oneshot
        commands = [c.strip() for c in args.commands.split(";")]
        print(f"[INFO] commands: {'; '.join(commands)}", flush=True)
        print("=" * 80, flush=True)
        result = run_cdb_oneshot(cdb, args.dump, symbols, commands, args.timeout)
        stdout = filter_noise(result.stdout)
        stderr = filter_noise(result.stderr)
        if stdout:
            print(stdout, end="" if stdout.endswith("\n") else "\n")
        if stderr:
            print(stderr, file=sys.stderr, end="" if stderr.endswith("\n") else "\n")
        if result.returncode != 0:
            sys.exit(result.returncode)
        return

    # Default triage: step-by-step streaming via Popen
    all_steps = TRIAGE_FAST + TRIAGE_DEEP
    total = len(all_steps)
    print(f"[INFO] Running {total} triage commands (streaming)...", flush=True)
    print("=" * 80, flush=True)

    cmd_args = [cdb, "-z", args.dump]
    if symbols:
        cmd_args.extend(["-y", symbols])
    cmd_args.extend(["-logo", "NUL"])

    proc = subprocess.Popen(
        cmd_args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    stop_event = threading.Event()
    stderr_thread = threading.Thread(target=_drain_stderr, args=(proc, stop_event), daemon=True)
    stderr_thread.start()

    _wait_for_prompt(proc)

    for i, (cmd, label) in enumerate(all_steps, 1):
        print(f"\n[STEP {i}/{total}] {label}: {cmd}", flush=True)
        if proc.poll() is not None:
            print(f"[ERROR] CDB exited unexpectedly (code {proc.returncode})", file=sys.stderr, flush=True)
            sys.exit(1)
        if not _run_step(proc, cmd):
            print("[ERROR] CDB is no longer responsive", file=sys.stderr, flush=True)
            sys.exit(1)

    # Clean exit
    stop_event.set()
    try:
        proc.stdin.write("q\n")
        proc.stdin.flush()
        proc.wait(timeout=10)
    except Exception:
        proc.kill()

    print(f"\n[INFO] Triage complete ({total} commands).", flush=True)


if __name__ == "__main__":
    main()
