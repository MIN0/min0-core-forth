"""Generate canonical raw bytecode used by both reference implementations."""

from __future__ import annotations

import json
from pathlib import Path

from demo import make_demo_program
from min0_core_forth_vm import Assembler, Op


ROOT = Path(__file__).resolve().parent
VECTOR_DIR = ROOT / "test_vectors"


def branch_program() -> bytes:
    asm = Assembler()
    asm.emit(Op.LIT, 0)
    asm.emit(Op.ZBRANCH, "zero")
    asm.emit(Op.LIT, 99)
    asm.emit(Op.BRANCH, "done")
    asm.label("zero")
    asm.emit(Op.LIT, 42)
    asm.label("done")
    asm.emit(Op.HALT)
    return asm.build()


def memory_program() -> bytes:
    asm = Assembler()
    asm.emit(Op.LIT, 0x12345678)
    asm.emit(Op.LIT, 0x1000)
    asm.emit(Op.STORE)
    asm.emit(Op.LIT, 0x1000)
    asm.emit(Op.FETCH)
    asm.emit(Op.HALT)
    return asm.build()


def main() -> None:
    VECTOR_DIR.mkdir(exist_ok=True)
    vectors = {
        "square_double": (make_demo_program(), [25, 14]),
        "zero_branch": (branch_program(), [42]),
        "memory": (memory_program(), [0x12345678]),
    }
    manifest = {"format": "MIN0 CORE FORTH raw bytecode v0.1", "vectors": {}}
    for name, (image, expected) in vectors.items():
        filename = f"{name}.fcb"
        (VECTOR_DIR / filename).write_bytes(image)
        manifest["vectors"][name] = {"file": filename, "expected_stack": expected}
    (VECTOR_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
