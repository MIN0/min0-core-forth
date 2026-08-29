"""Build a VM-resident dictionary and interpret tokens through it."""

from __future__ import annotations

import json
import hashlib

from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_outer import OuterInterpreter, install_core_primitives
from min0_core_forth_vm import Min0CoreForthVM


def build_demo() -> tuple[Min0CoreForthVM, RuntimeDictionary, OuterInterpreter]:
    vm = Min0CoreForthVM()
    dictionary = RuntimeDictionary(vm)
    install_core_primitives(dictionary)
    outer = OuterInterpreter(vm, dictionary)
    outer.interpret(": SQUARE DUP * ; : DOUBLE DUP + ;")
    return vm, dictionary, outer


if __name__ == "__main__":
    demo_vm, demo_dictionary, demo_outer = build_demo()
    result = demo_outer.interpret("5 SQUARE 7 DOUBLE")
    demo_outer.interpret("65 EMIT 66 EMIT CR 0x141 EMIT 0x1FF EMIT")
    demo_outer.interpret("WORDS")
    print(
        json.dumps(
            {
                "stack": result,
                "steps": demo_vm.steps,
                "return_depth": len(demo_vm.return_stack),
                "here": demo_dictionary.here,
                "latest": demo_dictionary.latest,
                "code_here": demo_outer.code_here,
                "code_hex": bytes(
                    demo_vm.memory[0x1000 : demo_outer.code_here]
                ).hex(),
                "dictionary_sha256": hashlib.sha256(
                    demo_dictionary.image()
                ).hexdigest(),
                "state": demo_outer.state,
                "output": demo_outer.output,
                "terminal_text": demo_outer.terminal_text,
            },
            separators=(",", ":"),
        )
    )
