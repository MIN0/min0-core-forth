"""Compile and execute IF/ELSE/THEN through the Python outer interpreter."""

from __future__ import annotations

import hashlib
import json

from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_outer import OuterInterpreter, install_core_primitives
from min0_core_forth_vm import Min0CoreForthVM


vm = Min0CoreForthVM()
dictionary = RuntimeDictionary(vm)
install_core_primitives(dictionary)
outer = OuterInterpreter(vm, dictionary)
outer.interpret(": CHOOSE IF 111 ELSE 222 THEN ;")
stack = outer.interpret("0 CHOOSE 1 CHOOSE")
print(
    json.dumps(
        {
            "stack": stack,
            "steps": vm.steps,
            "code_here": outer.code_here,
            "code_hex": bytes(vm.memory[0x1000 : outer.code_here]).hex(),
            "dictionary_sha256": hashlib.sha256(dictionary.image()).hexdigest(),
            "state": outer.state,
            "control_depth": len(outer.control_stack),
        },
        separators=(",", ":"),
    )
)
