# frozen_string_literal: true

require_relative "min0_core_forth_outer"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

def aligned(address)
  (address + 3) & ~3
end

def build_outer(limit: nil, install_primitives: true)
  vm = Min0CoreForth::VM.new
  dictionary = Min0CoreForth::RuntimeDictionary.new(vm, limit: limit)
  Min0CoreForth.install_core_primitives(dictionary) if install_primitives
  [vm, dictionary, Min0CoreForth::OuterInterpreter.new(vm, dictionary)]
end

vm, _dictionary, outer = build_outer
assert_equal([4, 9, 8, 4], outer.interpret("1 CELLS 5 CELL+ 5 ALIGNED 4 ALIGNED"), "cell address words")
vm.data_stack.clear
outer.interpret(": ADDRESS-OPS 3 CELLS 5 CELL+ 5 ALIGNED ;")
assert_equal([12, 9, 8], outer.interpret("ADDRESS-OPS"), "compiled cell address words")

_vm, _dictionary, outer = build_outer
assert_equal(
  [3, Min0CoreForth::CELL_MASK - 3, 0],
  outer.interpret("-1 CELL+ -1 CELLS -1 ALIGNED"),
  "cell address wrapping"
)

["CELL+", "CELLS", "ALIGNED"].each do |word|
  _vm, _dictionary, outer = build_outer
  begin
    outer.interpret(word)
    raise "#{word}: expected StackUnderflow"
  rescue Min0CoreForth::StackUnderflow
    puts "#{word} underflow: PASS"
  end
end

vm, dictionary, outer = build_outer
before = dictionary.here
outer.interpret("3 ALLOT HERE ALIGN HERE ALIGN HERE")
after = aligned(before + 3)
assert_equal([before + 3, after, after], vm.data_stack, "ALIGN HERE")
assert_equal(after, dictionary.here, "ALIGN idempotent")
assert_equal("\x00" * (after - before), vm.memory.byteslice(before, after - before), "ALIGN zero padding")

vm, dictionary, outer = build_outer
outer.interpret("CREATE TABLE 10 , 20 ,")
entry = dictionary.find("table")
assert_equal(Min0CoreForth::KIND_CREATED, entry.kind, "CREATE kind")
assert_equal(entry.xt + 8, entry.payload, "CREATE data field")
assert_equal(10, vm.read_cell(entry.payload), "CREATE first cell")
assert_equal(20, vm.read_cell(entry.payload + 4), "CREATE second cell")
assert_equal([entry.payload], outer.interpret("TABLE"), "CREATE interpret")
vm.data_stack.clear
outer.interpret(": SECOND TABLE CELL+ @ ;")
assert_equal([20], outer.interpret("SECOND"), "CREATE compile")

vm, dictionary, outer = build_outer
outer.interpret("CREATE BUFFER 7 ALLOT")
entry = dictionary.find("BUFFER")
assert_equal(entry.payload + 7, dictionary.here, "CREATE ALLOT size")
assert_equal("\x00" * 7, vm.memory.byteslice(entry.payload, 7), "CREATE ALLOT zero")
outer.interpret("99 CONSTANT AFTER")
assert_equal(entry.payload, dictionary.find("BUFFER").payload, "CREATE stable address")

vm, dictionary, outer = build_outer(
  limit: Min0CoreForth::DICTIONARY_BASE + 19,
  install_primitives: false
)
begin
  outer.interpret("CREATE X")
  raise "full CREATE: expected DictionaryFull"
rescue Min0CoreForth::DictionaryFull
  assert_equal(Min0CoreForth::DICTIONARY_BASE, dictionary.here, "CREATE failure HERE")
  assert_equal(0, dictionary.latest, "CREATE failure LATEST")
  assert_equal("", dictionary.image, "CREATE failure image")
  assert_equal(0, vm.read_cell(Min0CoreForth::DICTIONARY_BASE), "CREATE failure memory")
end

_vm, dictionary, outer = build_outer
begin
  outer.interpret("CREATE CREATE")
  raise "reserved CREATE name: expected CompileStateError"
rescue Min0CoreForth::CompileStateError
  assert_equal(nil, dictionary.find("CREATE"), "reserved CREATE absent")
end

puts "PASS: Ruby address/CREATE tests completed"
