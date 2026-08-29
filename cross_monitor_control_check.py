"""Compare Python and Ruby Monitor control-plane behavior."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from monitor_control_demo import run_demo


ROOT = Path(__file__).resolve().parent


def main() -> None:
    python_result = run_demo()
    completed = subprocess.run(
        ["ruby", "monitor_control_demo.rb"],
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
        raise SystemExit("FAIL: Monitor control implementations disagree")
    print(f"pause: {python_result['pause']}")
    print(f"budget: {python_result['budget']}")
    print(f"watchdog: {python_result['watchdog']}")
    print(f"final: {python_result['final']}")
    print("PASS: Python and Ruby Monitor control behavior agrees")


if __name__ == "__main__":
    main()
