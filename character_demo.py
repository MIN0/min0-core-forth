"""Build and read an 8-bit character body with the Python implementation."""

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
outer.interpret("CREATE TEXT 0x46 C, 0x4F C, 0x52 C, 0x54 C, 0x48 C,")
text_entry = dictionary.find("TEXT")
assert text_entry is not None
outer.interpret(": FIRST TEXT C@ ;")
outer.interpret(": THIRD TEXT 2 CHARS + C@ ;")
outer.interpret(": TEXT-END TEXT 5 CHARS + ;")
outer.interpret(': COMPILED-TEXT S" Compiled" ;')
outer.interpret(': COMPILED-OUTPUT ." Service" ;')
stack = outer.interpret("TEXT FIRST THIRD TEXT-END")
vm.data_stack.clear()
type_stack = outer.interpret("TEXT 5 TYPE")
quoted_stack = outer.interpret('S" Hello World" TYPE CR ." Done"')
compiled_stack = outer.interpret("COMPILED-TEXT")
outer.interpret("TYPE")
service_stack = outer.interpret("COMPILED-OUTPUT")
print(
    json.dumps(
        {
            "stack": stack,
            "type_stack": type_stack,
            "quoted_stack": quoted_stack,
            "compiled_stack": compiled_stack,
            "service_stack": service_stack,
            "output": outer.output,
            "terminal_text": outer.terminal_text,
            "steps": vm.steps,
            "text_address": text_entry.payload,
            "text_hex": bytes(vm.memory[text_entry.payload : text_entry.payload + 5]).hex(),
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
