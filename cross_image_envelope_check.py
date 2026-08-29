"""Compare Python and Ruby digest-bound image envelopes."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from image_envelope_demo import run_demo


ROOT = Path(__file__).resolve().parent


def main() -> None:
    python_result = run_demo()
    completed = subprocess.run(
        ["ruby", "image_envelope_demo.rb"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    ruby_result = json.loads(completed.stdout)
    python_result.pop("implementation")
    ruby_result.pop("implementation")
    print(f"identity:  {python_result['source_identity']}")
    print(f"records:   {python_result['record_count']}")
    print(f"rejected:  {python_result['rejected']}")
    print(f"auth:      {python_result['authentication']}")
    if python_result != ruby_result:
        print(f"Python: {python_result}")
        print(f"Ruby:   {ruby_result}")
        raise SystemExit("FAIL: image envelope implementations disagree")
    print("PASS: Python and Ruby image envelopes agree")


if __name__ == "__main__":
    main()
