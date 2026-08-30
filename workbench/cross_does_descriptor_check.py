"""Confirm Python and Ruby implement the same DOES descriptor model."""

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


python_result = run([sys.executable, "does_descriptor_demo.py"])
ruby_result = run(["ruby", "does_descriptor_demo.rb"])
if python_result != ruby_result:
    raise SystemExit(
        f"DOES descriptor mismatch:\nPython: {python_result}\nRuby:   {ruby_result}"
    )
print(json.dumps(python_result, sort_keys=True))
print("PASS: Python and Ruby DOES descriptor results match")
