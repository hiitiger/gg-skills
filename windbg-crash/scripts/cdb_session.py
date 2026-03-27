#!/usr/bin/env python3
"""
Persistent CDB session — loads the dump once, accepts commands interactively.

Usage:
  python cdb_session.py <dump_path> --symbols-file _symbols.txt

Protocol:
  - Script outputs "READY>" when ready for a command.
  - Send a line of semicolon-separated cdb commands via stdin.
  - Send "triage" to run the default triage command set (step-by-step with progress).
  - Output is streamed line-by-line (real-time) and terminated by "===CDB_OUTPUT_END===".
  - Send "quit" or "exit" to close the session.

This avoids re-launching cdb.exe (and re-loading the dump / symbols)
for every analysis phase.
"""
import argparse
import os
import sys
import subprocess
import threading

# Allow importing from the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdb_common import (
    find_cdb, resolve_symbols, filter_noise,
    TRIAGE_FAST, TRIAGE_DEEP, TRIAGE_COMMANDS, add_common_args,
)

OUTPUT_END_MARKER = "===CDB_OUTPUT_END==="
ECHO_SENTINEL = "__CDB_SESSION_SENTINEL__"
READY_PROMPT = "READY>"


def stderr_reader(proc, stop_event):
    """Drain stderr in a background thread to prevent blocking."""
    while not stop_event.is_set():
        line = proc.stderr.readline()
        if not line:
            break
        line = line.rstrip("\n").rstrip("\r")
        if line:
            filtered = filter_noise(line + "\n")
            if filtered.strip():
                print(f"[cdb stderr] {filtered.strip()}", file=sys.stderr, flush=True)


def start_cdb(cdb_path, dump_path, symbol_path):
    """Launch cdb.exe in interactive mode, return Popen handle."""
    args = [cdb_path, "-z", dump_path]
    if symbol_path:
        args.extend(["-y", symbol_path])
    args.extend(["-logo", "NUL"])

    proc = subprocess.Popen(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    return proc


def wait_for_initial_prompt(proc):
    """Read and stream CDB's initial banner until the first debugger prompt."""
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        filtered = filter_noise(line)
        if filtered:
            print(filtered, end="", flush=True)
        stripped = line.strip()
        # CDB prompts look like "0:000> " or "0:001> " etc.
        if stripped.endswith(">") and ":" in stripped:
            break


def send_command_streaming(proc, cmd_string):
    """Send commands to CDB, stream output line-by-line. Returns True on success."""
    full_cmd = f"{cmd_string}; .echo {ECHO_SENTINEL}\n"
    try:
        proc.stdin.write(full_cmd)
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

    # Consume the prompt line after the sentinel
    try:
        proc.stdout.readline()
    except (BrokenPipeError, OSError):
        pass
    return True


def run_triage(proc):
    """Run triage commands step-by-step with progress labels."""
    all_steps = TRIAGE_FAST + TRIAGE_DEEP
    total = len(all_steps)

    for i, (cmd, label) in enumerate(all_steps, 1):
        print(f"[STEP {i}/{total}] {label}: {cmd}", flush=True)
        if not send_command_streaming(proc, cmd):
            print("[ERROR] CDB process is no longer responsive", file=sys.stderr, flush=True)
            return False

    return True


def main():
    parser = argparse.ArgumentParser(description="Persistent CDB session for crash dump analysis")
    add_common_args(parser)
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
    print(f"[INFO] Loading dump (this may take a moment)...", flush=True)

    proc = start_cdb(cdb, args.dump, symbols)

    # Start stderr drainer
    stop_event = threading.Event()
    stderr_thread = threading.Thread(target=stderr_reader, args=(proc, stop_event), daemon=True)
    stderr_thread.start()

    # Wait for CDB to finish loading the dump (streams banner in real-time)
    wait_for_initial_prompt(proc)

    print(f"[INFO] Session ready. Send commands or 'triage' for initial analysis.", flush=True)
    print(READY_PROMPT, flush=True)

    try:
        while True:
            try:
                line = input()
            except EOFError:
                break

            line = line.strip()
            if not line:
                print(READY_PROMPT, flush=True)
                continue

            if line.lower() in ("quit", "exit"):
                break

            # Check if CDB is still alive
            if proc.poll() is not None:
                print(f"[ERROR] CDB process exited unexpectedly (code {proc.returncode})", file=sys.stderr, flush=True)
                sys.exit(1)

            if line.lower() == "triage":
                # Step-by-step triage with progress labels
                ok = run_triage(proc)
            else:
                # Arbitrary commands — stream output
                ok = send_command_streaming(proc, line)

            if not ok:
                print("[ERROR] CDB process is no longer responsive", file=sys.stderr, flush=True)
                sys.exit(1)

            print(OUTPUT_END_MARKER, flush=True)
            print(READY_PROMPT, flush=True)

    finally:
        # Clean shutdown
        stop_event.set()
        if proc.poll() is None:
            try:
                proc.stdin.write("q\n")
                proc.stdin.flush()
                proc.wait(timeout=10)
            except Exception:
                proc.kill()
        print("[INFO] Session closed.", flush=True)


if __name__ == "__main__":
    main()
