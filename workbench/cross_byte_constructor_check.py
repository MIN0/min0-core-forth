"""Confirm Python and Ruby C, constructor-plan results and traces agree."""

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run(command: list[str]) -> dict:
    completed = subprocess.run(
        command, cwd=ROOT, check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


python_result = run([sys.executable, "byte_constructor_demo.py"])
ruby_result = run(["ruby", "byte_constructor_demo.rb"])
if python_result != ruby_result:
    raise SystemExit(
        f"BYTE constructor mismatch:\nPython: {python_result}\nRuby:   {ruby_result}"
    )
print(json.dumps(python_result, sort_keys=True))
print("PASS: Python and Ruby BYTE C, constructor-plan results match")
