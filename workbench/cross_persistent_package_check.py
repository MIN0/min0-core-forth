"""Compare Python and Ruby bounded persistent-package behavior."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from persistent_package_demo import run_demo


ROOT = Path(__file__).resolve().parent


def main() -> None:
    python_result = run_demo()
    completed = subprocess.run(
        ["ruby", "persistent_package_demo.rb"],
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
        raise SystemExit("FAIL: persistent package implementations disagree")
    print(f"packages: {python_result['packages']}")
    print(f"rejected inputs: {len(python_result['rejected'])}")
    print("PASS: Python and Ruby persistent package behavior agrees")


if __name__ == "__main__":
    main()
