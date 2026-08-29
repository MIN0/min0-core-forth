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
stack = outer.interpret(": BUFFER: CREATE ALLOT ; 5 BUFFER: BUF BUF")
buffer_definer = dictionary.find("BUFFER:")
buffer = dictionary.find("BUF")
plan_address, behavior = dictionary.read_definer_descriptor(buffer_definer)
steps = dictionary.read_constructor_plan(buffer_definer)
allot = trace.events.find { |event| event[:event] == "constructor.allot" }
result = {
  behavior: behavior,
  body: buffer.payload,
  data_here: dictionary.data_here,
  event_names: trace.events.map { |event| event[:event] },
  plan: plan_address,
  plan_steps: steps,
  stack: stack,
  write_event: {
    details: allot[:details],
    explanation: allot[:basic_explanation],
    state: allot[:state]
  }
}
puts JSON.generate(result, ascii_only: true)
