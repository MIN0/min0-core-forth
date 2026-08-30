# frozen_string_literal: true

require "json"
require_relative "min0_core_forth_outer"

bus = Min0CoreForth::RegionMemory.new(
  0x10000,
  [
    Min0CoreForth::MemoryRegion.new(name: "CODE", start: 0, size: 0x4000, permissions: "rwx", programmable: true),
    Min0CoreForth::MemoryRegion.new(name: "DICTIONARY", start: 0x4000, size: 0x4000, permissions: "rw"),
    Min0CoreForth::MemoryRegion.new(name: "DATA", start: 0x8000, size: 0x8000, permissions: "rw")
  ]
)
vm = Min0CoreForth::VM.new(memory_bus: bus)
dictionary = Min0CoreForth::RuntimeDictionary.new(
  vm, base: 0x4000, limit: 0x8000, body_base: 0x8000, body_limit: 0x10000
)
Min0CoreForth.install_core_primitives(dictionary)
trace = Min0CoreForth::TraceRecorder.new("ruby")
outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary, trace: trace)
stack = outer.interpret(
  ": RECORD: CREATE C, ALLOT ALIGN ; 2 0x1AB RECORD: ITEM ITEM"
)
record_definer = dictionary.find("RECORD:")
item = dictionary.find("ITEM")
plan_address, behavior = dictionary.read_definer_descriptor(record_definer)
steps = dictionary.read_constructor_plan(record_definer)
action_names = ["constructor.c_comma", "constructor.allot", "constructor.align"]
action_events = trace.events.filter_map do |event|
  next unless action_names.include?(event[:event])

  {
    event: event[:event],
    details: event[:details],
    explanation: event[:basic_explanation],
    state: event[:state]
  }
end
result = {
  action_events: action_events,
  behavior: behavior,
  body: item.payload,
  body_bytes: vm.read_bytes(item.payload, 4).bytes,
  data_here: dictionary.data_here,
  event_names: trace.events.map { |event| event[:event] },
  plan: plan_address,
  plan_steps: steps,
  stack: stack
}
puts JSON.generate(result, ascii_only: true)
