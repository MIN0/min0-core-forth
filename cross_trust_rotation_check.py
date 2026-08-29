"""Compare Python and Ruby trust-bundle and rotation behavior."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from trust_rotation_demo import run_demo


ROOT = Path(__file__).resolve().parent


def main() -> None:
    python_result = run_demo()
    completed = subprocess.run(
        ["ruby", "trust_rotation_demo.rb"],
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
        raise SystemExit("FAIL: trust rotation implementations disagree")
    print(f"bundle cuts: {python_result['bundle_power_loss']}")
    print(f"ordering: {python_result['ordering']}")
    print("PASS: Python and Ruby trust rotation behavior agrees")


if __name__ == "__main__":
    main()
