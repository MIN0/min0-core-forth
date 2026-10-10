import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent


def run(command: list[str]) -> dict:
    completed = subprocess.run(
        command, cwd=HERE, check=True, capture_output=True, text=True
    )
    lines = [line for line in completed.stdout.splitlines() if line.startswith("{")]
    return json.loads(lines[-1])


def main() -> None:
    python_result = run([sys.executable, "virtual_assembler_demo.py"])
    ruby_result = run(["ruby", "virtual_assembler_demo.rb"])
    python_result.pop("implementation")
    ruby_result.pop("implementation")
    if python_result != ruby_result:
        raise SystemExit("Python/Ruby virtual assembler results differ")
    print("cross virtual assembler check: OK")


if __name__ == "__main__":
    main()
