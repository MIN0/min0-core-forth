"""Compare Python and Ruby authenticated DEFER switching."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from monitor_patch_demo import run_demo


ROOT = Path(__file__).resolve().parent


def main() -> None:
    python_result = run_demo()
    completed = subprocess.run(
        ["ruby", "monitor_patch_demo.rb"],
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
        raise SystemExit("FAIL: Monitor patch implementations disagree")
    print(f"paused stack: {python_result['first']['data_stack']}")
    print(f"audit: {python_result['audit']}")
    print(f"final stack: {python_result['final_stack']}")
    print("PASS: Python and Ruby authenticated DEFER switching agrees")


if __name__ == "__main__":
    main()
