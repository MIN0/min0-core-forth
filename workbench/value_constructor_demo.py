"""Create and execute VALUE: through a dictionary-resident constructor plan."""

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
    ": VALUE: CREATE , DOES> @ ; "
    "123 VALUE: ANSWER ANSWER : GET-ANSWER ANSWER ; GET-ANSWER"
)
value_definer = dictionary.find("VALUE:")
answer = dictionary.find("ANSWER")
assert value_definer is not None and answer is not None
plan_address, behavior = dictionary.read_definer_descriptor(value_definer)
steps = dictionary.read_constructor_plan(value_definer)
body, child_behavior = dictionary.read_does_descriptor(answer)
print(
    json.dumps(
        {
            "answer_kind": answer.kind,
            "behavior": behavior,
            "body": body,
            "body_value": vm.read_cell(body),
            "child_behavior": child_behavior,
            "data_here": dictionary.data_here,
            "header_here": dictionary.here,
            "plan": plan_address,
            "plan_steps": steps,
            "stack": stack,
            "value_kind": value_definer.kind,
        },
        sort_keys=True,
    )
)
