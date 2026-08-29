"""Build and use dictionary data definitions with the Python implementation."""

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
start_here = dictionary.here
outer.interpret("3 ALLOT")
comma_address = (dictionary.here + 3) & ~3
outer.interpret("0x12345678 ,")
outer.interpret("123 CONSTANT ANSWER")
outer.interpret("VARIABLE SLOT")
constant_entry = dictionary.find("ANSWER")
variable_entry = dictionary.find("SLOT")
assert constant_entry is not None and variable_entry is not None
outer.interpret(": USE ANSWER SLOT ! SLOT @ ;")
stack = outer.interpret("HERE USE")
print(
    json.dumps(
        {
            "stack": stack,
            "steps": vm.steps,
            "start_here": start_here,
            "final_here": dictionary.here,
            "latest": dictionary.latest,
            "comma_address": comma_address,
            "comma_value": vm.read_cell(comma_address),
            "constant": [constant_entry.kind, constant_entry.payload],
            "variable": [
                variable_entry.kind,
                variable_entry.payload,
                vm.read_cell(variable_entry.payload),
            ],
            "code_here": outer.code_here,
            "code_hex": bytes(vm.memory[0x1000 : outer.code_here]).hex(),
            "dictionary_sha256": hashlib.sha256(dictionary.image()).hexdigest(),
            "state": outer.state,
            "return_depth": len(vm.return_stack),
            "loop_depth": len(vm.loop_stack),
        },
        separators=(",", ":"),
    )
)
