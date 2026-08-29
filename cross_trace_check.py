"""Compare Python and Ruby semantic trace documents."""

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


python_trace = run([sys.executable, "trace_value_demo.py"])
ruby_trace = run(["ruby", "trace_value_demo.rb"])
python_implementation = python_trace.pop("implementation")
ruby_implementation = ruby_trace.pop("implementation")
if python_trace != ruby_trace:
    raise SystemExit("Python and Ruby semantic traces differ")
print(
    json.dumps(
        {
            "events": len(python_trace["events"]),
            "implementations": [python_implementation, ruby_implementation],
            "trace_format": python_trace["trace_format"],
        },
        sort_keys=True,
    )
)
print("PASS: Python and Ruby semantic traces match")
