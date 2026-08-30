"""Compare Python and Ruby W^X sealing and runtime-boundary behavior."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from sealed_execution_demo import run_demo


ROOT = Path(__file__).resolve().parent


def main() -> None:
    python_result = run_demo()
    completed = subprocess.run(
        ["ruby", "sealed_execution_demo.rb"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    ruby_result = json.loads(completed.stdout)
    python_result.pop("implementation")
    ruby_result.pop("implementation")
    if python_result != ruby_result:
        print(f"Python: {python_result}")
        print(f"Ruby:   {ruby_result}")
        raise SystemExit("FAIL: sealed execution implementations disagree")
    print("CODE permissions: rwx -> rx")
    print(f"verified entries: {python_result['verified_boundary_count']}")
    print("PASS: Python and Ruby sealed execution policies agree")


if __name__ == "__main__":
    main()
