# frozen_string_literal: true

require "json"
require_relative "min0_virtual_assembler"

sum_xor = <<~FORTH
  CODE: SUM-XOR ( a b c -- sum mix )
    IN  V0, a
    IN  V1, b
    IN  V2, c
    MOV V3, V0
    ADD V0, V1
    ADD V0, V2
    XOR V3, V1
    XOR V3, V2
    OUT sum, V0
    OUT mix, V3
  ;CODE
FORTH

definition = Min0VirtualAssembler.compile_code(sum_xor)
before = [10, 20, 30]
puts JSON.generate({
  format: "min0-virtual-assembler/0.1",
  implementation: "ruby",
  word: definition.name,
  inputs: definition.inputs,
  outputs: definition.outputs,
  before: before,
  after: definition.execute(before),
  instruction_count: definition.instructions.length
})
