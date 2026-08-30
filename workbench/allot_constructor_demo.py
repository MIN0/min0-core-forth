"""Create a byte buffer through the ALLOT constructor-plan action."""

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
stack = outer.interpret(": BUFFER: CREATE ALLOT ; 5 BUFFER: BUF BUF")
buffer_definer = dictionary.find("BUFFER:")
buffer = dictionary.find("BUF")
assert buffer_definer is not None and buffer is not None
plan_address, behavior = dictionary.read_definer_descriptor(buffer_definer)
steps = dictionary.read_constructor_plan(buffer_definer)
allot = next(event for event in trace.events if event["event"] == "constructor.allot")
print(
    json.dumps(
        {
            "behavior": behavior,
            "body": buffer.payload,
            "data_here": dictionary.data_here,
            "event_names": [event["event"] for event in trace.events],
            "plan": plan_address,
            "plan_steps": steps,
            "stack": stack,
            "write_event": {
                "details": allot["details"],
                "explanation": allot["basic_explanation"],
                "state": allot["state"],
            },
        },
        sort_keys=True,
    )
)
