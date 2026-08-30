"""Compile one source independently in Python and Ruby and compare images."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from min0_core_forth_compiler import compile_source
from min0_core_forth_vm import Min0CoreForthVM


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "examples" / "basic.fth"


def main() -> None:
    source_text = SOURCE.read_text(encoding="utf-8")
    python_image = compile_source(source_text)
    with tempfile.TemporaryDirectory() as temp_dir:
        ruby_image_path = Path(temp_dir) / "ruby.fcb"
        completed = subprocess.run(
            ["ruby", "run_source.rb", str(SOURCE), str(ruby_image_path)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        ruby_result = json.loads(completed.stdout)
        ruby_image = ruby_image_path.read_bytes()

    vm = Min0CoreForthVM()
    vm.load(python_image)
    python_result = {
        "stack": vm.run(),
        "steps": vm.steps,
        "image_bytes": len(python_image),
    }
    images_equal = python_image == ruby_image
    results_equal = python_result == ruby_result
    print(f"image bytes: {len(python_image)}")
    print(f"Python: {python_result}")
    print(f"Ruby:   {ruby_result}")
    print(f"byte-for-byte image match: {images_equal}")
    if not images_equal or not results_equal:
        raise SystemExit("FAIL: compiler implementations disagree")
    print("PASS: Python and Ruby compilers agree")


if __name__ == "__main__":
    main()
