#!/usr/bin/env python3
"""
Check _NT_SYMBOL_PATH environment variable.
Prints the current value or reports it's not set.
"""
import os
import sys

path = os.environ.get("_NT_SYMBOL_PATH", "")
if path:
    print(f"_NT_SYMBOL_PATH is set:")
    print(path)
    # Also show each path component for readability
    print(f"\nComponents ({len(path.split(';'))}):")
    for i, part in enumerate(path.split(";"), 1):
        part = part.strip()
        if part:
            print(f"  {i}. {part}")
else:
    print("_NT_SYMBOL_PATH is NOT set.", file=sys.stderr)
    sys.exit(1)
