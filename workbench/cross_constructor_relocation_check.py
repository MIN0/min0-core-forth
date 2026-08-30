"""Compare Python and Ruby typed-metadata relocation experiments."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from constructor_relocation_demo import run_demo


ROOT = Path(__file__).resolve().parent


def main() -> None:
    python_result = run_demo()
    completed = subprocess.run(
        ["ruby", "constructor_relocation_demo.rb"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    ruby_result = json.loads(completed.stdout)
    python_result.pop("implementation")
    ruby_result.pop("implementation")
    print(f"source bases: {python_result['source_bases']}")
    print(f"moved bases:  {python_result['moved_bases']}")
    print(f"relocations:  {python_result['relocation_count']} {python_result['target_counts']}")
    print(f"stack/body:   {python_result['stack']} / {python_result['body_hex']}")
    if python_result != ruby_result:
        print(f"Python: {python_result}")
        print(f"Ruby:   {ruby_result}")
        raise SystemExit("FAIL: constructor relocation implementations disagree")
    print("PASS: Python and Ruby relocate typed constructor metadata identically")


if __name__ == "__main__":
    main()
