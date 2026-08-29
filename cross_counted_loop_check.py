"""Compare Python and Ruby DO/LOOP/I compilation and execution."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run(command: list[str]) -> dict[str, object]:
    completed = subprocess.run(
        command, cwd=ROOT, check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


def main() -> None:
    python_result = run([sys.executable, "counted_loop_demo.py"])
    ruby_result = run(["ruby", "counted_loop_demo.rb"])
    print(f"Python: {python_result}")
    print(f"Ruby:   {ruby_result}")
    if python_result != ruby_result:
        raise SystemExit("FAIL: counted-loop implementations disagree")
    print("PASS: Python and Ruby counted-loop implementations agree")


if __name__ == "__main__":
    main()
