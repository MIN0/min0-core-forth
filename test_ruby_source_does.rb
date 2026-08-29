# frozen_string_literal: true

require_relative "min0_core_forth_outer"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

def make_source_does_system
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
  [vm, dictionary, Min0CoreForth::OuterInterpreter.new(vm, dictionary)]
end

vm, dictionary, outer = make_source_does_system
stack = outer.interpret(
  ": MAKER CREATE 7 + DOES> 1 + ; " \
  "5 MAKER CHILD CHILD : USE-CHILD CHILD ; USE-CHILD"
)
maker = dictionary.find("MAKER")
child = dictionary.find("CHILD")
plan_address, behavior = dictionary.read_definer_descriptor(maker)
constructor_steps = dictionary.read_constructor_plan(maker)
body, child_behavior = dictionary.read_does_descriptor(child)
assert_equal(Min0CoreForth::KIND_DEFINER, maker.kind, "definer kind")
assert_equal(Min0CoreForth::KIND_DOES, child.kind, "child kind")
assert_equal(0x8000, body, "child body")
assert_equal(behavior, child_behavior, "child behavior")
assert_equal(true, plan_address.between?(0x4000, 0x7FFF), "constructor plan region")
assert_equal(true, constructor_steps.first.first < behavior, "constructor before behavior")
assert_equal(Min0CoreForth::CONSTRUCTOR_ACTION_END, constructor_steps.last.last, "constructor END")
assert_equal([12, 0x8001, 0x8001], stack, "source DOES execution")
assert_equal([], vm.return_stack, "source DOES return stack")

vm, dictionary, outer = make_source_does_system
stack = outer.interpret(
  ": VALUE: CREATE , DOES> @ ; " \
  "123 VALUE: ANSWER ANSWER : GET-ANSWER ANSWER ; GET-ANSWER"
)
value_definer = dictionary.find("VALUE:")
answer = dictionary.find("ANSWER")
plan = dictionary.read_constructor_plan(value_definer)
body, = dictionary.read_does_descriptor(answer)
assert_equal(
  [Min0CoreForth::CONSTRUCTOR_ACTION_COMMA, Min0CoreForth::CONSTRUCTOR_ACTION_END],
  plan.map(&:last),
  "VALUE constructor plan"
)
assert_equal(0x8000, body, "VALUE body")
assert_equal(123, vm.read_cell(body), "VALUE stored cell")
assert_equal(0x8004, dictionary.data_here, "VALUE data HERE")
assert_equal([123, 123], stack, "VALUE execution")

vm, dictionary, outer = make_source_does_system
stack = outer.interpret(
  ": BYTE: CREATE C, DOES> C@ ; " \
  "0x1AB BYTE: FLAG FLAG"
)
byte_definer = dictionary.find("BYTE:")
flag = dictionary.find("FLAG")
plan = dictionary.read_constructor_plan(byte_definer)
body, = dictionary.read_does_descriptor(flag)
assert_equal(
  [Min0CoreForth::CONSTRUCTOR_ACTION_C_COMMA, Min0CoreForth::CONSTRUCTOR_ACTION_END],
  plan.map(&:last),
  "BYTE constructor plan"
)
assert_equal(0x8000, body, "BYTE body")
assert_equal(0xAB, vm.read_u8(body), "BYTE stored low byte")
assert_equal(0x8001, dictionary.data_here, "BYTE data HERE")
assert_equal([0xAB], stack, "BYTE execution")

vm.data_stack.clear
saved = [dictionary.here, dictionary.data_here, dictionary.latest]
begin
  outer.interpret("BYTE: EMPTY")
  raise "BYTE underflow: expected StackUnderflow"
rescue Min0CoreForth::StackUnderflow
  assert_equal([], vm.data_stack, "BYTE underflow stack")
  assert_equal(saved, [dictionary.here, dictionary.data_here, dictionary.latest], "BYTE underflow rollback")
  assert_equal(nil, dictionary.find("EMPTY", include_hidden: true), "BYTE underflow child absent")
end

vm, dictionary, outer = make_source_does_system
stack = outer.interpret(": BUFFER: CREATE ALLOT ; 5 BUFFER: BUF BUF")
buffer_definer = dictionary.find("BUFFER:")
buffer = dictionary.find("BUF")
plan = dictionary.read_constructor_plan(buffer_definer)
assert_equal(
  [Min0CoreForth::CONSTRUCTOR_ACTION_ALLOT, Min0CoreForth::CONSTRUCTOR_ACTION_END],
  plan.map(&:last),
  "BUFFER constructor plan"
)
assert_equal(0x8000, buffer.payload, "BUFFER body")
assert_equal(0x8005, dictionary.data_here, "BUFFER data HERE")
assert_equal([0x8000], stack, "BUFFER execution")

vm, dictionary, outer = make_source_does_system
outer.interpret(": BUFFER: CREATE ALLOT ;")
saved = [dictionary.here, dictionary.data_here, dictionary.latest]
begin
  outer.interpret("-1 BUFFER: BAD")
  raise "BUFFER negative: expected DictionaryError"
rescue Min0CoreForth::DictionaryError
  assert_equal([0xFFFF_FFFF], vm.data_stack, "BUFFER negative count preserved")
  assert_equal(saved, [dictionary.here, dictionary.data_here, dictionary.latest], "BUFFER negative rollback")
  assert_equal(nil, dictionary.find("BAD", include_hidden: true), "BUFFER negative child absent")
end

vm, dictionary, outer = make_source_does_system
outer.interpret(": BUFFER: CREATE ALLOT ;")
saved = [dictionary.here, dictionary.data_here, dictionary.latest]
begin
  outer.interpret("BUFFER: EMPTY")
  raise "BUFFER underflow: expected StackUnderflow"
rescue Min0CoreForth::StackUnderflow
  assert_equal([], vm.data_stack, "BUFFER underflow stack")
  assert_equal(saved, [dictionary.here, dictionary.data_here, dictionary.latest], "BUFFER underflow rollback")
  assert_equal(nil, dictionary.find("EMPTY", include_hidden: true), "BUFFER underflow child absent")
end

small_bus = Min0CoreForth::RegionMemory.new(
  0x10000,
  [
    Min0CoreForth::MemoryRegion.new(name: "CODE", start: 0, size: 0x4000, permissions: "rwx", programmable: true),
    Min0CoreForth::MemoryRegion.new(name: "DICTIONARY", start: 0x4000, size: 0x4000, permissions: "rw"),
    Min0CoreForth::MemoryRegion.new(name: "DATA", start: 0x8000, size: 2, permissions: "rw")
  ]
)
small_vm = Min0CoreForth::VM.new(memory_bus: small_bus)
small_dictionary = Min0CoreForth::RuntimeDictionary.new(
  small_vm, base: 0x4000, limit: 0x8000, body_base: 0x8000, body_limit: 0x8002
)
Min0CoreForth.install_core_primitives(small_dictionary)
small_outer = Min0CoreForth::OuterInterpreter.new(small_vm, small_dictionary)
small_outer.interpret(": BUFFER: CREATE ALLOT ;")
saved = [small_dictionary.here, small_dictionary.data_here, small_dictionary.latest]
begin
  small_outer.interpret("3 BUFFER: LARGE")
  raise "BUFFER full: expected DictionaryFull"
rescue Min0CoreForth::DictionaryFull
  assert_equal([3], small_vm.data_stack, "BUFFER full count preserved")
  assert_equal(saved, [small_dictionary.here, small_dictionary.data_here, small_dictionary.latest], "BUFFER full rollback")
  assert_equal(nil, small_dictionary.find("LARGE", include_hidden: true), "BUFFER full child absent")
end

vm, dictionary, outer = make_source_does_system
stack = outer.interpret(
  ": RECORD: CREATE C, ALLOT ALIGN ; " \
  "2 0x1AB RECORD: ITEM ITEM"
)
record_definer = dictionary.find("RECORD:")
item = dictionary.find("ITEM")
plan = dictionary.read_constructor_plan(record_definer)
assert_equal(
  [
    Min0CoreForth::CONSTRUCTOR_ACTION_C_COMMA,
    Min0CoreForth::CONSTRUCTOR_ACTION_ALLOT,
    Min0CoreForth::CONSTRUCTOR_ACTION_ALIGN,
    Min0CoreForth::CONSTRUCTOR_ACTION_END
  ],
  plan.map(&:last),
  "RECORD constructor plan"
)
assert_equal(0x8000, item.payload, "RECORD body")
assert_equal(0xAB, vm.read_u8(item.payload), "RECORD byte")
assert_equal([0, 0, 0], vm.read_bytes(0x8001, 3).bytes, "RECORD reserved and padding bytes")
assert_equal(0x8004, dictionary.data_here, "RECORD aligned data HERE")
assert_equal([0x8000], stack, "RECORD execution")

align_bus = Min0CoreForth::RegionMemory.new(
  0x10000,
  [
    Min0CoreForth::MemoryRegion.new(name: "CODE", start: 0, size: 0x4000, permissions: "rwx", programmable: true),
    Min0CoreForth::MemoryRegion.new(name: "DICTIONARY", start: 0x4000, size: 0x4000, permissions: "rw"),
    Min0CoreForth::MemoryRegion.new(name: "DATA", start: 0x8000, size: 3, permissions: "rw")
  ]
)
align_vm = Min0CoreForth::VM.new(memory_bus: align_bus)
align_dictionary = Min0CoreForth::RuntimeDictionary.new(
  align_vm, base: 0x4000, limit: 0x8000, body_base: 0x8000, body_limit: 0x8003
)
Min0CoreForth.install_core_primitives(align_dictionary)
align_outer = Min0CoreForth::OuterInterpreter.new(align_vm, align_dictionary)
align_outer.interpret(": RECORD: CREATE C, ALLOT ALIGN ;")
saved = [align_dictionary.here, align_dictionary.data_here, align_dictionary.latest]
begin
  align_outer.interpret("2 0x1AB RECORD: BAD")
  raise "ALIGN full: expected DictionaryFull"
rescue Min0CoreForth::DictionaryFull
  assert_equal([2, 0x1AB], align_vm.data_stack, "ALIGN full arguments preserved")
  assert_equal([0, 0, 0], align_vm.read_bytes(0x8000, 3).bytes, "ALIGN full data cleared")
  assert_equal(saved, [align_dictionary.here, align_dictionary.data_here, align_dictionary.latest], "ALIGN full rollback")
  assert_equal(nil, align_dictionary.find("BAD", include_hidden: true), "ALIGN full child absent")
end

vm, dictionary, outer = make_source_does_system
outer.interpret(": VALUE: CREATE , DOES> @ ;")
vm.data_stack.clear
saved = [dictionary.here, dictionary.data_here, dictionary.latest]
begin
  outer.interpret("VALUE: EMPTY")
  raise "VALUE underflow: expected StackUnderflow"
rescue Min0CoreForth::StackUnderflow
  assert_equal([], vm.data_stack, "VALUE underflow stack")
  assert_equal(saved, [dictionary.here, dictionary.data_here, dictionary.latest], "VALUE underflow rollback")
  assert_equal(nil, dictionary.find("EMPTY", include_hidden: true), "VALUE underflow child absent")
end

_vm, dictionary, outer = make_source_does_system
stack = outer.interpret(": MAKER CREATE ; MAKER PLAIN PLAIN")
maker = dictionary.find("MAKER")
plain = dictionary.find("PLAIN")
assert_equal(0, dictionary.read_definer_descriptor(maker)[1], "CREATE-only behavior")
assert_equal(Min0CoreForth::KIND_CREATED, plain.kind, "CREATE-only child kind")
assert_equal([0x8000], stack, "CREATE-only child execution")

_vm, dictionary, outer = make_source_does_system
outer.interpret(": MAKER CREATE DOES> ;")
saved = [dictionary.here, dictionary.data_here, dictionary.latest, outer.code_here]
[
  ": BAD 1 CREATE DOES> ;",
  ": BAD DOES> ;",
  ": BAD CREATE DOES> DOES> ;",
  ": BAD CREATE IF DOES> THEN ;"
].each do |source|
  begin
    outer.interpret(source)
    raise "malformed definer: expected CompileStateError"
  rescue Min0CoreForth::CompileStateError
    assert_equal(saved, [dictionary.here, dictionary.data_here, dictionary.latest, outer.code_here], "malformed rollback")
    assert_equal(nil, dictionary.find("BAD", include_hidden: true), "malformed word absent")
  end
end

small_vm = Min0CoreForth::VM.new
small_dictionary = Min0CoreForth::RuntimeDictionary.new(small_vm, limit: 0x8034)
small_outer = Min0CoreForth::OuterInterpreter.new(small_vm, small_dictionary)
small_outer.interpret(": MAKER CREATE DOES> ;")
saved = [small_dictionary.here, small_dictionary.data_here, small_dictionary.latest]
small_vm.push(123)
begin
  small_outer.interpret("MAKER CHILD")
  raise "child full: expected DictionaryFull"
rescue Min0CoreForth::DictionaryFull
  assert_equal([123], small_vm.data_stack, "child full stack rollback")
  assert_equal(saved, [small_dictionary.here, small_dictionary.data_here, small_dictionary.latest], "child full dictionary rollback")
  assert_equal(nil, small_dictionary.find("CHILD", include_hidden: true), "child full word absent")
end

puts "PASS: Ruby source DOES tests completed"
