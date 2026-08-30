"""Compile and execute extended counted loops with the Python implementation."""

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
outer.interpret(": EVENS 10 0 DO I 2 +LOOP ;")
outer.interpret(": DOWN -5 0 DO I -1 +LOOP ;")
outer.interpret(": ZERO 0 0 ?DO I LOOP ;")
outer.interpret(": PAIRS 2 0 DO 3 0 DO J I LOOP LOOP ;")
outer.interpret(": STOP 10 0 DO I DUP 3 = IF LEAVE THEN LOOP ;")
stack = outer.interpret("EVENS DOWN ZERO PAIRS STOP")
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
            "loop_depth": len(vm.loop_stack),
            "max_depths": [
                vm.max_data_depth,
                vm.max_return_depth,
                vm.max_loop_depth,
            ],
        },
        separators=(",", ":"),
    )
)
