"""Require Python and Ruby split-dictionary behavior to match exactly."""

import json
import subprocess
import sys


def run(command: list[str]) -> dict:
    completed = subprocess.run(
        command, check=True, capture_output=True, text=True, encoding="utf-8"
    )
    return json.loads(completed.stdout)


def main() -> None:
    python_result = run([sys.executable, "split_dictionary_demo.py"])
    ruby_result = run(["ruby", "split_dictionary_demo.rb"])
    print(f"Python: {python_result}")
    print(f"Ruby:   {ruby_result}")
    if python_result != ruby_result:
        raise SystemExit("FAIL: split dictionary implementations differ")
    print("PASS: Python and Ruby split dictionary implementations agree")


if __name__ == "__main__":
    main()
