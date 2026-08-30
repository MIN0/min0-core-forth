"""Compare Python and Ruby DEFER source semantics."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from defer_source_demo import run_demo


ROOT = Path(__file__).resolve().parent


def main() -> None:
    python_result = run_demo()
    completed = subprocess.run(
        ["ruby", "defer_source_demo.rb"],
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
        raise SystemExit("FAIL: DEFER source implementations disagree")
    print(f"first ACTION: {python_result['first_value']}")
    print(f"second ACTION: {python_result['second_value']}")
    print(f"ACTION-OF: 0x{python_result['second_action_xt']:08X}")
    print("PASS: Python and Ruby DEFER source semantics agree")


if __name__ == "__main__":
    main()
