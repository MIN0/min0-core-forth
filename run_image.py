"""Run one raw MIN0 CORE FORTH v0.1 image and print a machine-readable result."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from min0_core_forth_vm import Min0CoreForthVM


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    vm = Min0CoreForthVM()
    vm.load(args.image.read_bytes())
    stack = vm.run()
    print(json.dumps({"stack": stack, "steps": vm.steps}, separators=(",", ":")))


if __name__ == "__main__":
    main()
