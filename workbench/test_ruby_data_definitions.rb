# frozen_string_literal: true

require_relative "min0_core_forth_outer"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

def aligned(address)
  (address + Min0CoreForth::DICTIONARY_ALIGNMENT - 1) & ~(Min0CoreForth::DICTIONARY_ALIGNMENT - 1)
end

def build_outer(limit: nil, install_primitives: true)
  vm = Min0CoreForth::VM.new
  dictionary = Min0CoreForth::RuntimeDictionary.new(vm, limit: limit)
  Min0CoreForth.install_core_primitives(dictionary) if install_primitives
  [vm, dictionary, Min0CoreForth::OuterInterpreter.new(vm, dictionary)]
end

_vm, dictionary, outer = build_outer
outer.interpret("123 CONSTANT ANSWER")
entry = dictionary.find("answer")
assert_equal(Min0CoreForth::KIND_CONSTANT, entry.kind, "CONSTANT kind")
assert_equal(123, entry.payload, "CONSTANT payload")
assert_equal([123], outer.interpret("ANSWER"), "CONSTANT interpret")
outer.vm.data_stack.clear
outer.interpret(": DOUBLE-ANSWER ANSWER ANSWER + ;")
assert_equal([246], outer.interpret("DOUBLE-ANSWER"), "CONSTANT compile")

vm, dictionary, outer = build_outer
outer.interpret("VARIABLE SLOT")
entry = dictionary.find("SLOT")
assert_equal(Min0CoreForth::KIND_VARIABLE, entry.kind, "VARIABLE kind")
assert_equal(0, entry.payload % Min0CoreForth::DICTIONARY_ALIGNMENT, "VARIABLE alignment")
assert_equal(0, vm.read_cell(entry.payload), "VARIABLE zero initialization")
assert_equal([42], outer.interpret("42 SLOT ! SLOT @"), "VARIABLE interpret")
vm.data_stack.clear
outer.interpret(": SETGET 99 SLOT ! SLOT @ ;")
assert_equal([99], outer.interpret("SETGET"), "VARIABLE compile")
assert_equal(entry.payload, dictionary.find("SLOT").payload, "VARIABLE stable address")

vm, dictionary, outer = build_outer
before = dictionary.here
assert_equal([before + 3], outer.interpret("3 ALLOT HERE"), "ALLOT byte count")
outer.interpret("0x12345678 , HERE")
cell_address = aligned(before + 3)
assert_equal(0x12345678, vm.read_cell(cell_address), "comma value")
assert_equal([before + 3, cell_address + 4], vm.data_stack, "comma HERE alignment")
assert_equal("\x00" * 4, vm.memory.byteslice(before, cell_address - before), "ALLOT padding zero")

vm, dictionary, outer = build_outer
before = dictionary.here
outer.interpret("3 ALLOT VARIABLE ODD")
entry = dictionary.find("ODD")
raise "VARIABLE header was not aligned after ALLOT" if entry.header_address < aligned(before + 3)
puts "VARIABLE header follows ALLOT: PASS"
assert_equal(entry.xt + 8, entry.payload, "VARIABLE data follows header")
assert_equal(0, vm.read_cell(entry.payload), "realigned VARIABLE zero")
assert_equal(0, entry.header_address % Min0CoreForth::DICTIONARY_ALIGNMENT, "header alignment")

_vm, dictionary, outer = build_outer
saved_here = dictionary.here
begin
  outer.interpret("-1 ALLOT")
  raise "negative ALLOT: expected DictionaryError"
rescue Min0CoreForth::DictionaryError
  assert_equal([Min0CoreForth::CELL_MASK], outer.vm.data_stack, "negative ALLOT preserves count")
  assert_equal(saved_here, dictionary.here, "negative ALLOT preserves HERE")
end

vm, dictionary, outer = build_outer(
  limit: Min0CoreForth::DICTIONARY_BASE + 4,
  install_primitives: false
)
outer.interpret("7 ,")
assert_equal(7, vm.read_cell(Min0CoreForth::DICTIONARY_BASE), "comma initial data")
begin
  outer.interpret("8 ,")
  raise "full comma: expected DictionaryFull"
rescue Min0CoreForth::DictionaryFull
  assert_equal([8], vm.data_stack, "full comma preserves value")
  assert_equal(Min0CoreForth::DICTIONARY_BASE + 4, dictionary.here, "full comma preserves HERE")
  assert_equal(7, vm.read_cell(Min0CoreForth::DICTIONARY_BASE), "full comma preserves data")
end

vm, dictionary, outer = build_outer(
  limit: Min0CoreForth::DICTIONARY_BASE + 20,
  install_primitives: false
)
begin
  outer.interpret("VARIABLE X")
  raise "full VARIABLE: expected DictionaryFull"
rescue Min0CoreForth::DictionaryFull
  assert_equal(Min0CoreForth::DICTIONARY_BASE, dictionary.here, "VARIABLE rollback HERE")
  assert_equal(0, dictionary.latest, "VARIABLE rollback LATEST")
  assert_equal("", dictionary.image, "VARIABLE rollback image")
  assert_equal(0, vm.read_cell(Min0CoreForth::DICTIONARY_BASE), "VARIABLE rollback cell")
end

_vm, dictionary, outer = build_outer(limit: Min0CoreForth::DICTIONARY_BASE, install_primitives: false)
begin
  outer.interpret("9 CONSTANT X")
  raise "full CONSTANT: expected DictionaryFull"
rescue Min0CoreForth::DictionaryFull
  assert_equal([9], outer.vm.data_stack, "CONSTANT failure preserves value")
  assert_equal(Min0CoreForth::DICTIONARY_BASE, dictionary.here, "CONSTANT failure HERE")
  assert_equal(0, dictionary.latest, "CONSTANT failure LATEST")
end

["CONSTANT", "VARIABLE", "CREATE"].each do |source|
  _vm, _dictionary, outer = build_outer
  begin
    outer.interpret(source)
    raise "#{source}: expected CompileStateError"
  rescue Min0CoreForth::CompileStateError
    puts "#{source} missing name: PASS"
  end
end

[[",", Min0CoreForth::StackUnderflow], ["C,", Min0CoreForth::StackUnderflow], ["ALLOT", Min0CoreForth::StackUnderflow],
 ["CONSTANT X", Min0CoreForth::StackUnderflow]].each do |source, error|
  _vm, _dictionary, outer = build_outer
  begin
    outer.interpret(source)
    raise "#{source}: expected #{error}"
  rescue error
    puts "#{source} stack check: PASS"
  end
end

_vm, dictionary, outer = build_outer
outer.interpret("1")
begin
  outer.interpret("CONSTANT HERE")
  raise "reserved data name: expected CompileStateError"
rescue Min0CoreForth::CompileStateError
  assert_equal([1], outer.vm.data_stack, "reserved name preserves value")
  assert_equal(nil, dictionary.find("HERE"), "reserved name absent")
end

["HERE", ",", "C,", "ALLOT", "ALIGN", "CONSTANT", "VARIABLE"].each do |word|
  _vm, dictionary, outer = build_outer
  saved_here = dictionary.here
  saved_code_here = outer.code_here
  begin
    outer.interpret(": BAD #{word} ;")
    raise "#{word} compile: expected CompileStateError"
  rescue Min0CoreForth::CompileStateError
    assert_equal(Min0CoreForth::STATE_INTERPRET, outer.state, "data-word rollback state")
    assert_equal(saved_here, dictionary.here, "data-word rollback dictionary")
    assert_equal(saved_code_here, outer.code_here, "data-word rollback code")
    assert_equal(nil, dictionary.find("BAD", include_hidden: true), "data-word rollback name")
  end
end

puts "PASS: Ruby data-definition tests completed"
