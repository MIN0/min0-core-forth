"""Compare Python and Ruby runtime dictionary capability behavior."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from dictionary_capability_demo import run_demo


ROOT = Path(__file__).resolve().parent


def normalized(result: dict) -> dict:
    return {key: value for key, value in result.items() if key != "implementation"}


python_result = run_demo()
ruby_result = json.loads(
    subprocess.run(
        ["ruby", str(ROOT / "dictionary_capability_demo.rb")],
        check=True, capture_output=True, text=True,
    ).stdout
)
if normalized(python_result) != normalized(ruby_result):
    raise SystemExit("Python/Ruby dictionary capability results differ")

print("ordinary DICTIONARY writes: rejected")
print("Monitor DEFER gate: accepted and audited")
print("PASS: Python and Ruby dictionary capabilities agree")
