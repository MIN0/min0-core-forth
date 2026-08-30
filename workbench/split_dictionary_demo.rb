# frozen_string_literal: true

require "digest"
require "json"
require_relative "min0_core_forth_outer"

bus = Min0CoreForth::RegionMemory.new(
  0x10000,
  [
    Min0CoreForth::MemoryRegion.new(
      name: "CODE", start: 0x0000, size: 0x4000,
      permissions: "rwx", programmable: true
    ),
    Min0CoreForth::MemoryRegion.new(
      name: "DICTIONARY", start: 0x4000, size: 0x4000,
      permissions: "rw"
    ),
    Min0CoreForth::MemoryRegion.new(
      name: "DATA", start: 0x8000, size: 0x8000,
      permissions: "rw"
    )
  ]
)
vm = Min0CoreForth::VM.new(memory_bus: bus)
dictionary = Min0CoreForth::RuntimeDictionary.new(
  vm, base: 0x4000, limit: 0x8000, body_base: 0x8000, body_limit: 0x10000
)
Min0CoreForth.install_core_primitives(dictionary)
outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
stack = outer.interpret(
  "CREATE TABLE 10 , 20 , " \
  "VARIABLE FLAG " \
  ": SUM-TABLE TABLE @ TABLE CELL+ @ + ; " \
  "SUM-TABLE DUP FLAG ! FLAG @ TABLE"
)
table = dictionary.find("TABLE")
flag = dictionary.find("FLAG")
sum_table = dictionary.find("SUM-TABLE")
dictionary_image = dictionary.image

result = {
  stack: stack,
  steps: vm.steps,
  table: [table.header_address, table.payload],
  flag: [flag.header_address, flag.payload],
  sum_table: [sum_table.header_address, sum_table.payload],
  header_here: dictionary.here,
  data_here: dictionary.data_here,
  code_here: outer.code_here,
  body_hex: dictionary.body_image.unpack1("H*"),
  dictionary_sha256: Digest::SHA256.hexdigest(dictionary_image)
}
puts JSON.generate(result)
