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
outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
stack = outer.interpret(
  ": VALUE: CREATE , DOES> @ ; " \
  "123 VALUE: ANSWER ANSWER : GET-ANSWER ANSWER ; GET-ANSWER"
)
value_definer = dictionary.find("VALUE:")
answer = dictionary.find("ANSWER")
plan_address, behavior = dictionary.read_definer_descriptor(value_definer)
steps = dictionary.read_constructor_plan(value_definer)
body, child_behavior = dictionary.read_does_descriptor(answer)
puts JSON.generate(
  answer_kind: answer.kind,
  behavior: behavior,
  body: body,
  body_value: vm.read_cell(body),
  child_behavior: child_behavior,
  data_here: dictionary.data_here,
  header_here: dictionary.here,
  plan: plan_address,
  plan_steps: steps,
  stack: stack,
  value_kind: value_definer.kind
)
