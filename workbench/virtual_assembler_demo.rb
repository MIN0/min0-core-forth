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
maximum = Min0VirtualAssembler.compile_code(<<~FORTH)
  CODE: MAX ( a b -- max )
    IN V0, a
    IN V1, b
    CMP V0, V1
    BGE @a-wins
    OUT max, V1
    BRA @done
  @a-wins:
    OUT max, V0
  @done:
  ;CODE
FORTH
before = [10, 20, 30]
puts JSON.generate({
  format: "min0-virtual-assembler/0.1",
  implementation: "ruby",
  word: definition.name,
  inputs: definition.inputs,
  outputs: definition.outputs,
  before: before,
  after: definition.execute(before),
  instruction_count: definition.instructions.length,
  branch_results: [maximum.execute([10, 20]), maximum.execute([30, 20])]
})
