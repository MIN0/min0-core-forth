# frozen_string_literal: true

require "json"
require_relative "min0_core_forth_outer"

bus = Min0CoreForth::RegionMemory.new(
  0x10000,
  [
    Min0CoreForth::MemoryRegion.new(name: "CODE", start: 0x0000, size: 0x4000, permissions: "rwx", programmable: true),
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
outer.interpret("CREATE COUNTER 41 , : READ-PLUS-ONE @ 1 + ;")
counter = dictionary.find("COUNTER")
behavior = dictionary.find("READ-PLUS-ONE")
counter = dictionary.set_does(counter, behavior.payload)
body, code = dictionary.read_does_descriptor(counter)
interpreted = outer.interpret("COUNTER")[-1]
vm.data_stack.clear
compiled = outer.interpret(": USE-COUNTER COUNTER ; USE-COUNTER")[-1]

puts JSON.generate(
  body: body,
  code: code,
  compiled: compiled,
  descriptor: counter.payload,
  header_here: dictionary.here,
  interpreted: interpreted,
  kind: counter.kind
)
