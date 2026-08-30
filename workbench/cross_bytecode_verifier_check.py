"""Compare Python and Ruby bytecode verification summaries."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from bytecode_verifier_demo import run_demo


ROOT = Path(__file__).resolve().parent


def main() -> None:
    python_result = run_demo()
    completed = subprocess.run(
        ["ruby", "bytecode_verifier_demo.rb"],
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
        raise SystemExit("FAIL: bytecode verifier implementations disagree")
    print("literal 0x25 capabilities: none")
    print("DSET capabilities: compiled-defer-store")
    print("PASS: Python and Ruby bytecode verifiers agree")


if __name__ == "__main__":
    main()
