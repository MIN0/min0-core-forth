"""Emit typed CODE relocation records from a mixed FORTH definition set."""

from __future__ import annotations

import hashlib
import json
from collections import Counter

from constructor_image_fixture import make_system
from min0_core_forth_outer import DEFAULT_CODE_BASE, OuterInterpreter, install_core_primitives


SOURCE = """
VARIABLE SLOT
99 CONSTANT MARK
: INC 1 + ;
: CHOOSE IF 1 INC ELSE MARK THEN ;
: SPIN BEGIN DUP 3 < WHILE INC REPEAT ;
: SUM 0 3 0 DO I + LOOP ;
: SKIP 0 3 0 ?DO I 1 = IF LEAVE THEN I + LOOP ;
: STEP 0 4 0 DO I + 2 +LOOP ;
: VALUE: CREATE , DOES> @ ;
7 VALUE: ANSWER
: READ-ANSWER ANSWER ;
: SLOT-ADDR SLOT ;
"""


def run_demo(implementation: str = "python") -> dict:
    vm, dictionary = make_system()
    install_core_primitives(dictionary)
    outer = OuterInterpreter(vm, dictionary)
    outer.interpret(SOURCE)
    manifest = outer.relocation_manifest()
    canonical = ";".join(
        f"{record['section']}:{record['offset']}:{record['target']}:"
        f"{record['width']}:{record['kind']}"
        for record in manifest
    )
    kind_counts = Counter(str(record["kind"]) for record in manifest)
    stack = outer.interpret(
        "0 CHOOSE 1 CHOOSE 0 SPIN SUM SKIP STEP READ-ANSWER SLOT-ADDR"
    )
    answer_entry = dictionary.find("ANSWER")
    assert answer_entry is not None
    answer_body, _answer_behavior = dictionary.read_does_descriptor(answer_entry)
    return {
        "implementation": implementation,
        "manifest": manifest,
        "manifest_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "kind_counts": {kind: kind_counts[kind] for kind in sorted(kind_counts)},
        "target_counts": {
            target: sum(record["target"] == target for record in manifest)
            for target in ("code", "dictionary", "data")
        },
        "code_base": DEFAULT_CODE_BASE,
        "code_here": outer.code_here,
        "code_hex": vm.read_bytes(
            DEFAULT_CODE_BASE, outer.code_here - DEFAULT_CODE_BASE
        ).hex(),
        "stack": stack,
        "slot": dictionary.find("SLOT").payload,
        "answer": answer_body,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))
