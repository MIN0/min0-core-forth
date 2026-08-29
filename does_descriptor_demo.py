"""Exercise a DOES-style word across separate code, dictionary, and data regions."""

import json

from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_outer import OuterInterpreter, install_core_primitives
from min0_core_forth_vm import Min0CoreForthVM, MemoryRegion, RegionMemory


bus = RegionMemory(
    0x10000,
    [
        MemoryRegion("CODE", 0x0000, 0x4000, "rwx", programmable=True),
        MemoryRegion("DICTIONARY", 0x4000, 0x4000, "rw"),
        MemoryRegion("DATA", 0x8000, 0x8000, "rw"),
    ],
)
vm = Min0CoreForthVM(memory_bus=bus)
dictionary = RuntimeDictionary(
    vm, base=0x4000, limit=0x8000, body_base=0x8000, body_limit=0x10000
)
install_core_primitives(dictionary)
outer = OuterInterpreter(vm, dictionary)
outer.interpret("CREATE COUNTER 41 , : READ-PLUS-ONE @ 1 + ;")
counter = dictionary.find("COUNTER")
behavior = dictionary.find("READ-PLUS-ONE")
assert counter is not None and behavior is not None
counter = dictionary.set_does(counter, behavior.payload)
body, code = dictionary.read_does_descriptor(counter)
interpreted = outer.interpret("COUNTER")[-1]
vm.data_stack.clear()
compiled = outer.interpret(": USE-COUNTER COUNTER ; USE-COUNTER")[-1]

print(
    json.dumps(
        {
            "body": body,
            "code": code,
            "compiled": compiled,
            "descriptor": counter.payload,
            "header_here": dictionary.here,
            "interpreted": interpreted,
            "kind": counter.kind,
        },
        sort_keys=True,
    )
)
