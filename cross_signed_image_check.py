"""Compare Python and Ruby Ed25519 image-envelope behavior."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from signed_image_demo import run_demo


ROOT = Path(__file__).resolve().parent


def main() -> None:
    python_result = run_demo()
    completed = subprocess.run(
        ["ruby", "signed_image_demo.rb"],
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
        raise SystemExit("FAIL: signed image implementations disagree")
    print(f"identity: {python_result['identity']}")
    print(f"rejected: {python_result['rejected']}")
    print("PASS: Python and Ruby signed image behavior agrees")


if __name__ == "__main__":
    main()
