"""Compare Python and Ruby recovery boot and repair transitions."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from recovery_path_demo import run_demo


ROOT = Path(__file__).resolve().parent


def main() -> None:
    python_result = run_demo()
    completed = subprocess.run(
        ["ruby", "recovery_path_demo.rb"],
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
        raise SystemExit("FAIL: recovery path implementations disagree")
    print(f"recovery boot: {python_result['recovery_boot']}")
    print(f"repair cuts: {python_result['repair_power_loss']}")
    print("PASS: Python and Ruby recovery path behavior agrees")


if __name__ == "__main__":
    main()
