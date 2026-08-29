"""Combine C,, ALLOT, and ALIGN in one constructor plan."""

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
stack = outer.interpret(
    ": RECORD: CREATE C, ALLOT ALIGN ; 2 0x1AB RECORD: ITEM ITEM"
)
record_definer = dictionary.find("RECORD:")
item = dictionary.find("ITEM")
assert record_definer is not None and item is not None
plan_address, behavior = dictionary.read_definer_descriptor(record_definer)
steps = dictionary.read_constructor_plan(record_definer)
action_names = {"constructor.c_comma", "constructor.allot", "constructor.align"}
action_events = [
    {
        "event": event["event"],
        "details": event["details"],
        "explanation": event["basic_explanation"],
        "state": event["state"],
    }
    for event in trace.events
    if event["event"] in action_names
]
print(
    json.dumps(
        {
            "action_events": action_events,
            "behavior": behavior,
            "body": item.payload,
            "body_bytes": list(vm.read_bytes(item.payload, 4)),
            "data_here": dictionary.data_here,
            "event_names": [event["event"] for event in trace.events],
            "plan": plan_address,
            "plan_steps": steps,
            "stack": stack,
        },
        sort_keys=True,
    )
)
