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
  ": MAKER CREATE 7 + DOES> 1 + ; " \
  "5 MAKER CHILD CHILD : USE-CHILD CHILD ; USE-CHILD"
)
maker = dictionary.find("MAKER")
child = dictionary.find("CHILD")
plan_address, behavior = dictionary.read_definer_descriptor(maker)
constructor_steps = dictionary.read_constructor_plan(maker)
body, child_behavior = dictionary.read_does_descriptor(child)
puts JSON.generate(
  behavior: behavior,
  body: body,
  child_behavior: child_behavior,
  child_kind: child.kind,
  constructor_plan: plan_address,
  constructor_steps: constructor_steps,
  data_here: dictionary.data_here,
  definer_kind: maker.kind,
  header_here: dictionary.here,
  stack: stack
)
