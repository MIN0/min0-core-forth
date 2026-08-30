"""Compare Python and Ruby A/B power-loss state transitions."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from transactional_install_demo import run_demo


ROOT = Path(__file__).resolve().parent


def main() -> None:
    python_result = run_demo()
    completed = subprocess.run(
        ["ruby", "transactional_install_demo.rb"],
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
        raise SystemExit("FAIL: transactional install implementations disagree")
    print(f"install cuts: {python_result['install_power_loss']}")
    print(f"trusted cuts: {python_result['trust_power_loss']}")
    print("PASS: Python and Ruby transactional install behavior agrees")


if __name__ == "__main__":
    main()
