"""Compile a defining word, create its child, and run it."""

import json

from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_outer import OuterInterpreter, install_core_primitives
from min0_core_forth_vm import Min0CoreForthVM, MemoryRegion, RegionMemory


bus = RegionMemory(
    0x10000,
    [
        MemoryRegion("CODE", 0, 0x4000, "rwx", programmable=True),
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
stack = outer.interpret(
    ": MAKER CREATE 7 + DOES> 1 + ; "
    "5 MAKER CHILD CHILD : USE-CHILD CHILD ; USE-CHILD"
)
maker = dictionary.find("MAKER")
child = dictionary.find("CHILD")
assert maker is not None and child is not None
plan_address, behavior = dictionary.read_definer_descriptor(maker)
constructor_steps = dictionary.read_constructor_plan(maker)
body, child_behavior = dictionary.read_does_descriptor(child)
print(
    json.dumps(
        {
            "behavior": behavior,
            "body": body,
            "child_behavior": child_behavior,
            "child_kind": child.kind,
            "constructor_plan": plan_address,
            "constructor_steps": constructor_steps,
            "data_here": dictionary.data_here,
            "definer_kind": maker.kind,
            "header_here": dictionary.here,
            "stack": stack,
        },
        sort_keys=True,
    )
)
