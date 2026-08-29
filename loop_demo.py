"""Compile and execute loop words through the Python outer interpreter."""

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
outer.interpret(": COUNTDOWN BEGIN 1 - DUP 0 = UNTIL ;")
outer.interpret(": DOWN BEGIN 0 OVER < WHILE 1 - REPEAT ;")
stack = outer.interpret("3 COUNTDOWN 4 DOWN")
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
            "return_depth": len(vm.return_stack),
        },
        separators=(",", ":"),
    )
)
