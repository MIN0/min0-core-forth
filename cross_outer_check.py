"""Compare Python and Ruby interpret-state outer interpreters."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run(command: list[str]) -> dict[str, object]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(completed.stdout)


def main() -> None:
    python_result = run([sys.executable, "outer_demo.py"])
    ruby_result = run(["ruby", "outer_demo.rb"])
    print("Python: " + json.dumps(python_result, ensure_ascii=True, sort_keys=True))
    print("Ruby:   " + json.dumps(ruby_result, ensure_ascii=True, sort_keys=True))
    if python_result != ruby_result:
        raise SystemExit("FAIL: outer interpreter implementations disagree")
    print("PASS: Python and Ruby outer interpreters agree")


if __name__ == "__main__":
    main()
