"""Build CREATE data fields and execute address words in Python."""

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
outer.interpret("CREATE TABLE 10 , 20 ,")
outer.interpret("CREATE BUFFER 3 CELLS ALLOT")
table = dictionary.find("TABLE")
buffer = dictionary.find("BUFFER")
assert table is not None and buffer is not None
outer.interpret(": TOTAL TABLE @ TABLE CELL+ @ + ;")
outer.interpret(": BUFFER-END BUFFER 3 CELLS + ;")
stack = outer.interpret("TABLE TOTAL BUFFER BUFFER-END")
print(
    json.dumps(
        {
            "stack": stack,
            "steps": vm.steps,
            "table": [
                table.kind,
                table.payload,
                vm.read_cell(table.payload),
                vm.read_cell(table.payload + 4),
            ],
            "buffer": [buffer.kind, buffer.payload, dictionary.find("BUFFER").payload],
            "final_here": dictionary.here,
            "latest": dictionary.latest,
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
