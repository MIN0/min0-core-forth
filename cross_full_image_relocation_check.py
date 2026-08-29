"""Compare Python and Ruby relocation of a mixed executable image."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from full_image_relocation_demo import run_demo


ROOT = Path(__file__).resolve().parent


def main() -> None:
    python_result = run_demo()
    completed = subprocess.run(
        ["ruby", "full_image_relocation_demo.rb"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    ruby_result = json.loads(completed.stdout)
    python_result.pop("implementation")
    ruby_result.pop("implementation")
    print(
        f"relocations: CODE={python_result['code_relocations']} "
        f"DICTIONARY={python_result['dictionary_relocations']}"
    )
    print(f"stack:       {python_result['stack']}")
    print(
        f"moved data:  SLOT=0x{python_result['slot']:X} "
        f"ANSWER=0x{python_result['answer_body']:X}"
    )
    if python_result != ruby_result:
        print(f"Python: {python_result}")
        print(f"Ruby:   {ruby_result}")
        raise SystemExit("FAIL: full image relocation implementations disagree")
    print("PASS: Python and Ruby relocate and execute the full mixed image identically")


if __name__ == "__main__":
    main()
