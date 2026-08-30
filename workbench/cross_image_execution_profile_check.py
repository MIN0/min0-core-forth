"""Compare Python and Ruby signed image execution-profile policy."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from image_execution_profile_demo import run_demo


ROOT = Path(__file__).resolve().parent


def main() -> None:
    python_result = run_demo()
    completed = subprocess.run(
        ["ruby", "image_execution_profile_demo.rb"],
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
        raise SystemExit("FAIL: image execution-profile implementations disagree")
    print(
        "profiles: "
        f"{python_result['safe_image_profile']} / "
        f"{python_result['build_image_profile']}"
    )
    print("PASS: Python and Ruby image execution-profile policy agrees")


if __name__ == "__main__":
    main()
