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
stack = outer.interpret(": BYTE: CREATE C, DOES> C@ ; 0x1AB BYTE: FLAG FLAG")
byte_definer = dictionary.find("BYTE:")
flag = dictionary.find("FLAG")
plan_address, behavior = dictionary.read_definer_descriptor(byte_definer)
steps = dictionary.read_constructor_plan(byte_definer)
body, child_behavior = dictionary.read_does_descriptor(flag)
c_comma = trace.events.find { |event| event[:event] == "constructor.c_comma" }
result = {
  behavior: behavior,
  body: body,
  child_behavior: child_behavior,
  data_here: dictionary.data_here,
  event_names: trace.events.map { |event| event[:event] },
  plan: plan_address,
  plan_steps: steps,
  stack: stack,
  stored_byte: vm.read_u8(body),
  write_event: {
    details: c_comma[:details],
    explanation: c_comma[:basic_explanation],
    state: c_comma[:state]
  }
}
puts JSON.generate(result, ascii_only: true)
