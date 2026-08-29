"""Compare verified compiled dot-quote service execution across hosts."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from service_output_demo import run_demo


ROOT = Path(__file__).resolve().parent


def main() -> None:
    python_result = run_demo()
    completed = subprocess.run(
        ["ruby", "service_output_demo.rb"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    ruby_result = json.loads(completed.stdout)
    python_result.pop("implementation")
    ruby_result.pop("implementation")
    print(f"service IDs: {python_result['service_ids']}")
    print(f"output:      {python_result['terminal_text']}")
    print(
        "permissions: "
        f"CODE={python_result['code_permissions']} "
        f"DATA={python_result['data_permissions']}"
    )
    if python_result != ruby_result:
        print(f"Python: {python_result}")
        print(f"Ruby:   {ruby_result}")
        raise SystemExit("FAIL: verified output-service implementations disagree")
    print("PASS: compiled dot-quote uses the same sealed service boundary")


if __name__ == "__main__":
    main()
