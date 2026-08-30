"""Compare compiled-string relocation and read-only execution across hosts."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from compiled_string_relocation_demo import run_demo


ROOT = Path(__file__).resolve().parent


def main() -> None:
    python_result = run_demo()
    completed = subprocess.run(
        ["ruby", "compiled_string_relocation_demo.rb"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    ruby_result = json.loads(completed.stdout)
    python_result.pop("implementation")
    ruby_result.pop("implementation")
    print(f"address:     0x{python_result['address']:08X}")
    print(f"output:      {python_result['terminal_text']}")
    print(f"permissions: {python_result['data_permissions']}")
    if python_result != ruby_result:
        print(f"Python: {python_result}")
        print(f"Ruby:   {ruby_result}")
        raise SystemExit("FAIL: compiled-string relocation implementations disagree")
    print("PASS: compiled string relocates and runs from read-only DATA")


if __name__ == "__main__":
    main()
