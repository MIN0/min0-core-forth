"""Compare independently generated Python and Ruby dictionary images."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run_json(command: list[str]) -> dict[str, object]:
    completed = subprocess.run(
        command, cwd=ROOT, check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        python_image = temp / "python.dict"
        ruby_image = temp / "ruby.dict"
        python_result = run_json([sys.executable, "dictionary_fixture.py", str(python_image)])
        ruby_result = run_json(["ruby", "dictionary_fixture.rb", str(ruby_image)])
        bytes_equal = python_image.read_bytes() == ruby_image.read_bytes()

    metadata_equal = python_result == ruby_result
    print(f"dictionary bytes: {python_result['bytes']}")
    print(f"base/HERE/LATEST: {python_result['base']:#06x} / {python_result['here']:#06x} / {python_result['latest']:#06x}")
    print(f"entries newest-first: {[entry['name'] for entry in python_result['entries']]}")
    print(f"byte-for-byte image match: {bytes_equal}")
    print(f"metadata match: {metadata_equal}")
    if not bytes_equal or not metadata_equal:
        raise SystemExit("FAIL: runtime dictionary implementations disagree")
    print("PASS: Python and Ruby runtime dictionaries agree")


if __name__ == "__main__":
    main()
