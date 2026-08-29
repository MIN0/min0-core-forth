"""Compare Python and Ruby HMAC-SHA256/Ed25519 authentication vectors."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from auth_comparison_demo import run_demo


ROOT = Path(__file__).resolve().parent


def main() -> None:
    python_result = run_demo()
    completed = subprocess.run(
        ["ruby", "auth_comparison_demo.rb"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    ruby_result = json.loads(completed.stdout)
    print(f"Python timing: {python_result['timing']}")
    print(f"Ruby timing:   {ruby_result['timing']}")
    python_result.pop("implementation")
    ruby_result.pop("implementation")
    python_result.pop("timing")
    ruby_result.pop("timing")
    print(f"sizes:      {python_result['sizes']}")
    print(f"verification: {python_result['verification']}")
    print(f"compromise: {python_result['device_compromise']}")
    if python_result != ruby_result:
        print(f"Python: {python_result}")
        print(f"Ruby:   {ruby_result}")
        raise SystemExit("FAIL: authentication comparison implementations disagree")
    print("PASS: Python and Ruby authentication vectors agree")


if __name__ == "__main__":
    main()
