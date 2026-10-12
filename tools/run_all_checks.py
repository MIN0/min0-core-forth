"""Run the Python, Ruby, and cross-language MIN0 validation gates."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / "workbench"


def run(label: str, command: list[str], *, cwd: Path = ROOT) -> bool:
    print(f"\n=== {label} ===", flush=True)
    result = subprocess.run(command, cwd=cwd, check=False)
    if result.returncode == 0:
        print(f"PASS: {label}", flush=True)
        return True
    print(f"FAIL: {label} (exit {result.returncode})", flush=True)
    return False


def main() -> int:
    failures: list[str] = []
    if not run(
        "Python unittest suite",
        [sys.executable, "-m", "unittest", "discover", "-s", "workbench", "-p", "test_*.py"],
    ):
        failures.append("Python unittest suite")

    ruby_tests = sorted(WORKBENCH.glob("test_ruby*.rb"))
    for path in ruby_tests:
        label = path.name
        if not run(label, ["ruby", str(path)]):
            failures.append(label)

    cross_checks = sorted(WORKBENCH.glob("cross*.py"))
    for path in cross_checks:
        label = path.name
        # Cross-check scripts intentionally invoke their sibling demo files by
        # relative name. Keep that public contract independent of the shell's
        # original working directory.
        if not run(label, [sys.executable, str(path)], cwd=WORKBENCH):
            failures.append(label)

    print("\n=== SUMMARY ===")
    print(
        f"Python suites: 1, Ruby files: {len(ruby_tests)}, "
        f"cross-language checks: {len(cross_checks)}"
    )
    if failures:
        print(f"FAILED ({len(failures)}): " + ", ".join(failures))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
