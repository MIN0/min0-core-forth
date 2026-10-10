# frozen_string_literal: true

require_relative "min0_virtual_assembler"

SUM_XOR = <<~FORTH
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

def assert_equal(expected, actual, label)
  raise "#{label}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual
end

definition = Min0VirtualAssembler.compile_code(SUM_XOR)
before = [10, 20, 30]
assert_equal([60, 0], definition.execute(before), "three inputs to two outputs")
assert_equal([10, 20, 30], before, "caller stack remains unchanged")
assert_equal([99, 60, 0], definition.execute([99, 10, 20, 30]), "prefix preserved")

inc = Min0VirtualAssembler.compile_code(<<~FORTH)
  CODE: INC ( x -- y )
    IN V0, x
    LIT V1, 1
    ADD V0, V1
    OUT y, V0
  ;CODE
FORTH
assert_equal([0], inc.execute([0xFFFF_FFFF]), "32-bit wrapping")

constant = Min0VirtualAssembler.compile_code(
  "CODE: ANSWER ( -- value )\n LIT V0, 42\n OUT value, V0\n ;CODE"
)
discard = Min0VirtualAssembler.compile_code("CODE: DISCARD ( value -- )\n ;CODE")
assert_equal([7, 42], constant.execute([7]), "empty input contract")
assert_equal([7], discard.execute([7, 42]), "empty output contract")

begin
  Min0VirtualAssembler.compile_code("CODE: BAD ( x -- y )\n IN V0, x\n ;CODE")
  raise "missing output was accepted"
rescue Min0VirtualAssembler::VerifyError => error
  raise unless error.message.include?("not assigned")
end

begin
  definition.execute([10, 20])
  raise "stack underflow was accepted"
rescue Min0VirtualAssembler::StackUnderflow
  # Expected.
end

puts "ruby virtual assembler tests: OK"
