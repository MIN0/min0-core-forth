"""Verify Python and Ruby VMs against the exact same bytecode files."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run_json(command: list[str]) -> dict[str, object]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def main() -> None:
    manifest = json.loads((ROOT / "test_vectors" / "manifest.json").read_text())
    failures = 0
    for name, definition in manifest["vectors"].items():
        image = ROOT / "test_vectors" / definition["file"]
        expected = definition["expected_stack"]
        python_result = run_json([sys.executable, "run_image.py", str(image)])
        ruby_result = run_json(["ruby", "run_image.rb", str(image)])
        passed = (
            python_result["stack"] == expected
            and ruby_result["stack"] == expected
            and python_result == ruby_result
        )
        print(
            f"{name}: Python={python_result} Ruby={ruby_result} "
            f"expected={expected} {'PASS' if passed else 'FAIL'}"
        )
        failures += 0 if passed else 1
    if failures:
        raise SystemExit(f"{failures} cross-language vector(s) failed")
    print("PASS: Python and Ruby implementations agree")


if __name__ == "__main__":
    main()
