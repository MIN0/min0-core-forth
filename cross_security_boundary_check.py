"""Compare Python and Ruby executable threat-boundary audits."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from security_boundary_demo import run_demo


ROOT = Path(__file__).resolve().parent


def main() -> None:
    python_result = run_demo()
    completed = subprocess.run(
        ["ruby", "security_boundary_demo.rb"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    ruby_result = json.loads(completed.stdout)
    python_result.pop("implementation")
    ruby_result.pop("implementation")
    for scenario in python_result["scenarios"]:
        print(
            f"{scenario['id']} {scenario['scenario']}: "
            f"{scenario['result']} ({scenario['status']})"
        )
    if python_result != ruby_result:
        print(f"Python: {python_result}")
        print(f"Ruby:   {ruby_result}")
        raise SystemExit("FAIL: security boundary audits disagree")
    print("PASS: Python and Ruby security boundary audits agree")


if __name__ == "__main__":
    main()
