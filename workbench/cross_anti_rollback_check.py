"""Compare Python and Ruby anti-rollback behavior and fixed vectors."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from anti_rollback_demo import run_demo


ROOT = Path(__file__).resolve().parent


def main() -> None:
    python_result = run_demo()
    completed = subprocess.run(
        ["ruby", "anti_rollback_demo.rb"],
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
        raise SystemExit("FAIL: anti-rollback implementations disagree")
    print(f"identities: {python_result['identities']}")
    print(f"trusted state: {python_result['trusted_state']}")
    print("PASS: Python and Ruby anti-rollback behavior agrees")


if __name__ == "__main__":
    main()
