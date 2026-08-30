"""Compare Python and Ruby compiler-emitted relocation manifests."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from code_relocation_demo import run_demo


ROOT = Path(__file__).resolve().parent


def main() -> None:
    python_result = run_demo()
    completed = subprocess.run(
        ["ruby", "code_relocation_demo.rb"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    ruby_result = json.loads(completed.stdout)
    python_result.pop("implementation")
    ruby_result.pop("implementation")
    print(f"relocations: {len(python_result['manifest'])}")
    print(f"kinds:       {python_result['kind_counts']}")
    print(f"targets:     {python_result['target_counts']}")
    print(f"stack:       {python_result['stack']}")
    if python_result != ruby_result:
        print(f"Python: {python_result}")
        print(f"Ruby:   {ruby_result}")
        raise SystemExit("FAIL: compiler relocation manifests disagree")
    print("PASS: Python and Ruby compiler relocation manifests agree")


if __name__ == "__main__":
    main()
