"""Create and execute BYTE: through the C, constructor-plan action."""

import json

from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_outer import OuterInterpreter, install_core_primitives
from min0_core_forth_trace import TraceRecorder
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
trace = TraceRecorder("python")
outer = OuterInterpreter(vm, dictionary, trace=trace)
stack = outer.interpret(": BYTE: CREATE C, DOES> C@ ; 0x1AB BYTE: FLAG FLAG")
byte_definer = dictionary.find("BYTE:")
flag = dictionary.find("FLAG")
assert byte_definer is not None and flag is not None
plan_address, behavior = dictionary.read_definer_descriptor(byte_definer)
steps = dictionary.read_constructor_plan(byte_definer)
body, child_behavior = dictionary.read_does_descriptor(flag)
c_comma = next(event for event in trace.events if event["event"] == "constructor.c_comma")
print(
    json.dumps(
        {
            "behavior": behavior,
            "body": body,
            "child_behavior": child_behavior,
            "data_here": dictionary.data_here,
            "event_names": [event["event"] for event in trace.events],
            "plan": plan_address,
            "plan_steps": steps,
            "stack": stack,
            "stored_byte": vm.read_u8(body),
            "write_event": {
                "details": c_comma["details"],
                "explanation": c_comma["basic_explanation"],
                "state": c_comma["state"],
            },
        },
        sort_keys=True,
    )
)
