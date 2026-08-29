"""Compare Python and Ruby loader capability-boundary behavior."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from capability_boundary_demo import run_demo


ROOT = Path(__file__).resolve().parent


def main() -> None:
    python_result = run_demo()
    completed = subprocess.run(
        ["ruby", "capability_boundary_demo.rb"],
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
        raise SystemExit("FAIL: capability-boundary implementations disagree")
    print(f"permissions: {python_result['permissions']}")
    print(f"rejected operations: {len(python_result['denied'])}")
    print(f"recovery repair: {python_result['recovery_repair']}")
    print("PASS: Python and Ruby capability-boundary behavior agrees")


if __name__ == "__main__":
    main()
