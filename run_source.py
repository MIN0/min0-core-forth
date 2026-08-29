"""Compile and execute minimal MIN0 CORE FORTH source."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from min0_core_forth_compiler import compile_source
from min0_core_forth_vm import Min0CoreForthVM


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--write-image", type=Path)
    args = parser.parse_args()
    image = compile_source(args.source.read_text(encoding="utf-8"))
    if args.write_image:
        args.write_image.write_bytes(image)
    vm = Min0CoreForthVM()
    vm.load(image)
    stack = vm.run()
    print(
        json.dumps(
            {"stack": stack, "steps": vm.steps, "image_bytes": len(image)},
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
