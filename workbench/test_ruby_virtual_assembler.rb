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
assert_equal([20], maximum.execute([10, 20]), "branch chooses b")
assert_equal([30], maximum.execute([30, 20]), "branch chooses a")

looping = Min0VirtualAssembler.compile_code(<<~FORTH)
  CODE: LOOP-MAYBE ( flag -- )
    IN V0, flag
    LIT V1, 0
  @again:
    CMP V0, V1
    BEQ @done
    BRA @again
  @done:
  ;CODE
FORTH
begin
  looping.execute([1], max_steps: 20)
  raise "instruction budget was ignored"
rescue Min0VirtualAssembler::ExecutionError
  # Expected.
end

memory = Min0VirtualAssembler::MemoryWindow.new(0x1000, 16)
memory.write32(0x1004, 0x12345678)
load_pair = Min0VirtualAssembler.compile_code(<<~FORTH)
  CODE: LOAD-PAIR ( address -- first second )
    IN V1, address
    LD32 V0, [V1]
    LD32 V2, [V1-4]
    OUT first, V0
    OUT second, V2
  ;CODE
FORTH
assert_equal([0, 0x12345678], load_pair.execute([0x1008], memory: memory), "checked load")

spaced_load = Min0VirtualAssembler.compile_code(<<~FORTH)
  CODE: SPACED-LOAD ( address -- value )
    IN V1, address
    LD32 V0, [ V1 - 4 ]
    OUT value, V0
  ;CODE
FORTH
assert_equal([0x12345678], spaced_load.execute([0x1008], memory: memory), "spaced address")

data_window = Min0VirtualAssembler::MemoryWindow.new(0, 8)
io_window = Min0VirtualAssembler::MemoryWindow.new(0, 8)
data_window.write32(0, 11)
io_window.write32(0, 22)
capabilities = Min0VirtualAssembler::MemoryCapabilities.new(
  { "DATA" => data_window, "IO" => io_window }, default: "DATA"
)
read_both = Min0VirtualAssembler.compile_code(<<~FORTH)
  CODE: READ-BOTH ( address -- data io default )
    IN V3, address
    LD32 V0, [ DATA: V3 ]
    LD32 V1, [IO:V3]
    LD32 V2, [V3]
    OUT data, V0
    OUT io, V1
    OUT default, V2
  ;CODE
FORTH
assert_equal([11, 22, 11], read_both.execute([0], memory: capabilities), "named capabilities")

round_trip = Min0VirtualAssembler.compile_code(<<~FORTH)
  CODE: ROUND-TRIP ( value address -- observed )
    IN V0, value
    IN V1, address
    ST32 [V1], V0
    LD32 V2, [V1]
    OUT observed, V2
  ;CODE
FORTH
assert_equal([55], round_trip.execute([55, 0x1000], memory: memory), "staged store forwarding")
assert_equal(55, memory.read32(0x1000), "committed store")

store_then_loop = Min0VirtualAssembler.compile_code(<<~FORTH)
  CODE: STORE-THEN-LOOP ( value address -- )
    IN V0, value
    IN V1, address
    ST32 [V1], V0
  @again:
    CMP V0, V0
    BEQ @again
  ;CODE
FORTH
memory.write32(0x1000, 7)
begin
  store_then_loop.execute([88, 0x1000], memory: memory, max_steps: 10)
  raise "failed store was committed"
rescue Min0VirtualAssembler::ExecutionError
  assert_equal(7, memory.read32(0x1000), "failed store remains uncommitted")
end

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
