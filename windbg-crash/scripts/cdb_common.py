#!/usr/bin/env python3
"""
Shared utilities for CDB/WinDbg crash dump analysis scripts.

Provides common functions for finding cdb.exe, resolving symbol paths,
filtering noisy output, and default triage commands.
"""
import os
import re
import subprocess
import sys


DEFAULT_CDB = r"C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe"

# Triage commands split into fast (no symbol download) and deep (triggers symbol resolution).
# Fast commands run first so the AI gets actionable data within seconds.
TRIAGE_FAST = [
    ("!sym quiet",     "Suppressing symbol noise"),
    ("||",             "Dump type"),
    ("|",              "Process info"),
    (".time",          "Timestamps"),
    ("vertarget",      "Target info"),
    (".exr -1",        "Exception record"),
    (".ecxr",          "Setting exception context"),
    ("r",              "Registers"),
    ("lm",             "Loaded modules"),
]

TRIAGE_DEEP = [
    (".kframes 100",   "Increasing stack depth"),
    ("kp",             "Call stack with parameters"),
    ("!analyze -v",    "Full crash analysis (may download symbols)"),
]

# Combined list for backward compatibility (flat command strings only)
TRIAGE_COMMANDS = [cmd for cmd, _ in TRIAGE_FAST + TRIAGE_DEEP]

NOISE_PATTERNS = [
    re.compile(r"^DBGHELP:.*is not a valid store\s*$"),
    re.compile(r"^NatVis script unloaded from "),
    re.compile(r"^SYMSRV:  "),
    re.compile(r"^\*{4} WARNING: Unable to verify checksum for "),
]


def find_cdb(user_path=None):
    """Locate cdb.exe: user-provided path > default path > PATH search."""
    if user_path and os.path.isfile(user_path):
        return user_path
    if os.path.isfile(DEFAULT_CDB):
        return DEFAULT_CDB
    for p in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(p, "cdb.exe")
        if os.path.isfile(candidate):
            return candidate
    return None


def resolve_symbols(args_symbols=None, args_symbols_file=None):
    """Resolve symbol path from file, arg, or env var."""
    if args_symbols_file:
        try:
            with open(args_symbols_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except OSError as e:
            print(f"[WARN] Cannot read symbols file: {e}", file=sys.stderr)
    if args_symbols:
        return args_symbols
    return os.environ.get("_NT_SYMBOL_PATH", "")


def filter_noise(output):
    """Remove repetitive DBGHELP, NatVis, and SYMSRV noise lines."""
    lines = output.splitlines(keepends=True)
    return "".join(l for l in lines if not any(p.match(l) for p in NOISE_PATTERNS))


def run_cdb_oneshot(cdb_path, dump_path, symbol_path, commands, timeout=600):
    """Launch cdb.exe, run commands, quit. Returns subprocess.CompletedProcess."""
    cmd_string = "; ".join(commands) + "; q"
    args = [cdb_path, "-z", dump_path, "-c", cmd_string]
    if symbol_path:
        args.extend(["-y", symbol_path])
    args.extend(["-logo", "NUL"])

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return result
    except subprocess.TimeoutExpired:
        print(f"[ERROR] cdb timed out after {timeout} seconds", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"[ERROR] cdb not found at: {cdb_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


def add_common_args(parser):
    """Add common CLI arguments (--cdb, --symbols, --symbols-file, --timeout) to an argparse parser."""
    parser.add_argument("dump", help="Path to the .dmp file")
    parser.add_argument("--cdb", default=None, help=f"Path to cdb.exe (default: {DEFAULT_CDB})")
    parser.add_argument("--symbols", "-y", default=None, help="Symbol path (_NT_SYMBOL_PATH format)")
    parser.add_argument("--symbols-file", default=None,
                        help="Read symbol path from a text file (avoids shell escaping issues with UNC paths)")
    parser.add_argument("--timeout", "-t", type=int, default=600, help="Timeout in seconds (default: 600)")
