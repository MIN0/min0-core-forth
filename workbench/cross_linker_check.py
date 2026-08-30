"""Compare Python and Ruby transactional linker validation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from linker_validation_demo import run_demo


ROOT = Path(__file__).resolve().parent


def main() -> None:
    python_result = run_demo()
    completed = subprocess.run(
        ["ruby", "linker_validation_demo.rb"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    ruby_result = json.loads(completed.stdout)
    python_result.pop("implementation")
    ruby_result.pop("implementation")
    print(f"records:  {python_result['record_count']}")
    print(f"rejected: {python_result['rejected']}")
    print(f"code:     {python_result['code_hex']}")
    if python_result != ruby_result:
        print(f"Python: {python_result}")
        print(f"Ruby:   {ruby_result}")
        raise SystemExit("FAIL: transactional linker implementations disagree")
    print("PASS: Python and Ruby transactional linkers agree")


if __name__ == "__main__":
    main()
