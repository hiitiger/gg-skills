#!/usr/bin/env python3
"""
Run arbitrary cdb commands against a dump file with streaming output.

Usage:
  python run_cdb_cmd.py <dump_path> <commands> [--symbols <path>] [--symbols-file <file>]

Symbol path resolution order:
  1. --symbols-file <file>  (read from text file, avoids shell escaping)
  2. --symbols <path>       (direct command line)
  3. _NT_SYMBOL_PATH env var

Example:
  python run_cdb_cmd.py crash.dmp "!heap -p -a 0x12345; !address 0x12345"
  python run_cdb_cmd.py crash.dmp "!address -summary" --symbols-file sym.txt

Output is streamed line-by-line so partial results appear immediately
even when symbol downloads are slow.
"""
import argparse
import os
import sys
import subprocess
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdb_common import (
    find_cdb, resolve_symbols, filter_noise,
    add_common_args,
)


def _drain_stderr(proc, stop_event):
    """Drain stderr in background to prevent blocking."""
    while not stop_event.is_set():
        line = proc.stderr.readline()
        if not line:
            break
        filtered = filter_noise(line)
        if filtered.strip():
            print(f"[cdb stderr] {filtered.strip()}", file=sys.stderr, flush=True)


def main():
    parser = argparse.ArgumentParser(description="Run cdb commands on a dump")
    add_common_args(parser)
    parser.add_argument("commands", help="Semicolon-separated cdb commands")
    args = parser.parse_args()

    if not os.path.isfile(args.dump):
        print(f"[ERROR] Dump file not found: {args.dump}", file=sys.stderr)
        sys.exit(1)

    cdb = find_cdb(args.cdb)
    if not cdb:
        print("[ERROR] cdb.exe not found", file=sys.stderr)
        sys.exit(1)

    symbols = resolve_symbols(args.symbols, args.symbols_file)

    # Build command string: suppress noise, run user commands, quit
    cmd_string = "!sym quiet; " + args.commands.strip().rstrip(";") + "; q"

    cmd_args = [cdb, "-z", args.dump, "-c", cmd_string]
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

    # Stream stdout line-by-line
    try:
        for line in proc.stdout:
            filtered = filter_noise(line)
            if filtered:
                print(filtered, end="", flush=True)
    except (BrokenPipeError, OSError):
        pass

    proc.wait(timeout=args.timeout)
    stop_event.set()

    if proc.returncode != 0:
        print(f"[ERROR] cdb exited with code {proc.returncode}", file=sys.stderr)
        sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
