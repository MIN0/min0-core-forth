"""Check the user-facing Python and Ruby quiet launchers against one source."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ': GREET ." Hello from both hosts" ; GREET CR'


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, text=True, capture_output=True, check=False, encoding="utf-8"
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "cross-cli.fth"
        source.write_text(SOURCE, encoding="utf-8", newline="\n")
        python = run([sys.executable, str(ROOT / "min0_forth.py"), "-z", str(source)])
        ruby = run(["ruby", str(ROOT / "min0_forth.rb"), "-z", str(source)])
    expected = "Hello from both hosts\n"
    if python.returncode or ruby.returncode:
        print(f"Python stderr: {python.stderr!r}", file=sys.stderr)
        print(f"Ruby stderr:   {ruby.stderr!r}", file=sys.stderr)
        return 1
    if python.stdout != expected or ruby.stdout != expected or python.stdout != ruby.stdout:
        print(f"Python: {python.stdout!r}", file=sys.stderr)
        print(f"Ruby:   {ruby.stdout!r}", file=sys.stderr)
        return 1
    print(f"output: {expected!r}")
    print("PASS: Python and Ruby quiet launchers agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
