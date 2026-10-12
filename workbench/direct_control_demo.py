"""Emit a stable summary of Python direct-control behavior."""

from __future__ import annotations

import json

from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_outer import OuterInterpreter, install_core_primitives
from min0_core_forth_vm import Min0CoreForthVM


vm = Min0CoreForthVM()
dictionary = RuntimeDictionary(vm)
install_core_primitives(dictionary)
outer = OuterInterpreter(vm, dictionary)
outer.interpret("1 IF 10 ELSE 20 THEN")
outer.interpret("0 BEGIN 1 + DUP 3 = UNTIL")
outer.interpret("5 2 DO I LOOP")
outer.interpret("2 FOR I DUP 0 = IF 8 ELSE 9 THEN NEXT")
print(
    json.dumps(
        {
            "stack": vm.data_stack,
            "output": outer.terminal_text,
            "state": outer.state,
            "loop_depth": len(vm.loop_stack),
        },
        separators=(",", ":"),
    )
)
