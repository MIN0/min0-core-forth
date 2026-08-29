"""Compare Python and Ruby compile-state DEFER profiles."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from compiled_defer_demo import run_demo


ROOT = Path(__file__).resolve().parent


def main() -> None:
    python_result = run_demo()
    completed = subprocess.run(
        ["ruby", "compiled_defer_demo.rb"],
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
        raise SystemExit("FAIL: compiled DEFER profile implementations disagree")
    print(f"safe [']: 0x{python_result['safe_literal_xt']:08X}")
    print(f"safe ACTION-OF: 0x{python_result['safe_current_xt']:08X}")
    print(
        "standard-build switch: "
        f"{python_result['build_before_switch']} -> "
        f"{python_result['build_after_switch']}"
    )
    print("PASS: Python and Ruby compiled DEFER profiles agree")


if __name__ == "__main__":
    main()
