# frozen_string_literal: true

require_relative "min0_core_forth_outer"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

def build_outer
  vm = Min0CoreForth::VM.new
  dictionary = Min0CoreForth::RuntimeDictionary.new(vm)
  Min0CoreForth.install_core_primitives(dictionary)
  vm.load([Min0CoreForth::Op::DUP, Min0CoreForth::Op::MUL, Min0CoreForth::Op::EXIT].pack("C*"), address: 0x100)
  vm.load([Min0CoreForth::Op::DUP, Min0CoreForth::Op::ADD, Min0CoreForth::Op::EXIT].pack("C*"), address: 0x110)
  dictionary.add_colon("SQUARE", 0x100)
  dictionary.add_colon("DOUBLE", 0x110)
  [vm, dictionary, Min0CoreForth::OuterInterpreter.new(vm, dictionary)]
end

vm, _dictionary, outer = build_outer
assert_equal([25, 14], outer.interpret("5 SQUARE 7 DOUBLE"), "numbers and colon words")
assert_equal([], vm.return_stack, "balanced return stack")

_vm, _dictionary, outer = build_outer
assert_equal([9], outer.interpret("3 DUP *"), "primitive execution")

_vm, _dictionary, outer = build_outer
assert_equal([], outer.interpret("2 3 4 * + ."), "dot emits late multiplication result")
assert_equal([], outer.interpret("2 3 * 4 + ."), "dot emits early multiplication result")
assert_equal([], outer.interpret("0 1 - ."), "dot emits signed result")
assert_equal(["14", "10", "-1"], outer.output, "dot output sequence")

_vm, _dictionary, outer = build_outer
begin
  outer.interpret(".")
  raise "dot underflow: expected StackUnderflow"
rescue Min0CoreForth::StackUnderflow
  assert_equal([], outer.output, "dot underflow preserves output")
end

_vm, _dictionary, outer = build_outer
assert_equal([], outer.interpret("65 EMIT 66 EMIT CR"), "EMIT and CR consume no remaining data")
assert_equal(["A", "B", "\n"], outer.output, "EMIT and CR output fragments")
assert_equal("AB\n", outer.terminal_text, "exact terminal stream")

_vm, _dictionary, outer = build_outer
assert_equal([], outer.interpret("0x141 EMIT 0x1FF EMIT"), "EMIT low eight bits")
assert_equal("Aÿ", outer.terminal_text, "EMIT low-byte character mapping")

_vm, _dictionary, outer = build_outer
begin
  outer.interpret("EMIT")
  raise "EMIT underflow: expected StackUnderflow"
rescue Min0CoreForth::StackUnderflow
  assert_equal([], outer.output, "EMIT underflow preserves output")
end

[".", "EMIT", "CR", "WORDS"].each do |name|
  begin
    outer.interpret(": #{name} DUP ;")
    raise "#{name} definition: expected CompileStateError"
  rescue Min0CoreForth::CompileStateError
    assert_equal(Min0CoreForth::STATE_INTERPRET, outer.state, "#{name} definition rollback")
  end
end

_vm, _dictionary, outer = build_outer
outer.interpret(": CUBE DUP DUP * * ; : SQUARE DUP + ; WORDS")
startup, user = outer.terminal_text.split(
  "--- ここから先はユーザーが : で定義したワードなどです ---"
)
startup_words = startup.split
user_words = user.split
assert_equal(true, startup_words.include?("WORDS"), "WORDS lists itself as startup word")
assert_equal(true, startup_words.include?("DOUBLE"), "WORDS lists startup dictionary word")
assert_equal(false, startup_words.include?("SQUARE"), "WORDS removes shadowed startup word")
assert_equal(true, user_words.include?("CUBE"), "WORDS lists user colon word")
assert_equal(1, user_words.count("SQUARE"), "WORDS lists active redefinition once")

_vm, dictionary, outer = build_outer
dictionary.add_colon("SECRET", 0x100, hidden: true)
outer.interpret("WORDS")
assert_equal(true, outer.terminal_text.include?("（まだありません）"), "WORDS empty user section")
assert_equal(false, outer.terminal_text.include?("SECRET"), "WORDS omits hidden word")

_vm, _dictionary, outer = build_outer
assert_equal([18], outer.interpret("8 double \\ ignore\n 2 +"), "case and comment")

_vm, _dictionary, outer = build_outer
outer.interpret("6")
assert_equal([36], outer.interpret("SQUARE"), "state persists")

_vm, dictionary, outer = build_outer
dictionary.add_colon("SECRET", 0x100, hidden: true)
begin
  outer.interpret("SECRET")
  raise "hidden word: expected UnknownWord"
rescue Min0CoreForth::UnknownWord
  puts "hidden word: PASS"
end

begin
  outer.interpret("MISSING")
  raise "unknown word: expected UnknownWord"
rescue Min0CoreForth::UnknownWord
  puts "unknown word: PASS"
end

vm, dictionary, outer = build_outer
initial_code_here = outer.code_here
assert_equal([27], outer.interpret(": CUBE DUP DUP * * ; 3 CUBE"), "interactive definition")
cube = dictionary.find("CUBE")
assert_equal(initial_code_here, cube.payload, "interactive code address")
assert_equal(
  [Min0CoreForth::Op::DUP, Min0CoreForth::Op::DUP, Min0CoreForth::Op::MUL, Min0CoreForth::Op::MUL, Min0CoreForth::Op::EXIT],
  vm.memory.byteslice(initial_code_here, outer.code_here - initial_code_here).bytes,
  "interactive code bytes"
)
assert_equal(Min0CoreForth::STATE_INTERPRET, outer.state, "interpret state restored")

_vm, dictionary, outer = build_outer
outer.interpret(": QUAD")
assert_equal(Min0CoreForth::STATE_COMPILE, outer.state, "compile state across input")
assert_equal(nil, dictionary.find("QUAD"), "building word hidden")
outer.interpret("DOUBLE DOUBLE ;")
assert_equal([12], outer.interpret("3 QUAD"), "definition across input")

_vm, _dictionary, outer = build_outer
outer.interpret(": SQUARE DUP + ;")
assert_equal([10], outer.interpret("5 SQUARE"), "latest redefinition wins")

_vm, dictionary, outer = build_outer
saved_dictionary_here = dictionary.here
saved_latest = dictionary.latest
saved_code_here = outer.code_here
begin
  outer.interpret(": BROKEN 1 MISSING ;")
  raise "compile rollback: expected UnknownWord"
rescue Min0CoreForth::UnknownWord
  assert_equal(Min0CoreForth::STATE_INTERPRET, outer.state, "rollback state")
  assert_equal(saved_dictionary_here, dictionary.here, "rollback dictionary HERE")
  assert_equal(saved_latest, dictionary.latest, "rollback LATEST")
  assert_equal(saved_code_here, outer.code_here, "rollback code HERE")
  assert_equal(nil, dictionary.find("BROKEN", include_hidden: true), "rollback hidden word")
end

begin
  outer.interpret(";")
  raise "semicolon outside definition: expected CompileStateError"
rescue Min0CoreForth::CompileStateError
  puts "semicolon outside definition: PASS"
end

bus = Min0CoreForth::RegionMemory.new(
  0x10000,
  [
    Min0CoreForth::MemoryRegion.new(
      name: "CODE", start: 0x0000, size: 0x8000,
      permissions: "rwx", programmable: true
    ),
    Min0CoreForth::MemoryRegion.new(
      name: "DICTIONARY", start: 0x8000, size: 0x8000,
      permissions: "rw"
    )
  ]
)
vm = Min0CoreForth::VM.new(memory_bus: bus)
dictionary = Min0CoreForth::RuntimeDictionary.new(vm)
Min0CoreForth.install_core_primitives(dictionary)
outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
assert_equal([25], outer.interpret(": SQUARE DUP * ; 5 SQUARE"), "split-region outer execution")
assert_equal(false, dictionary.find("SQUARE").nil?, "split-region dictionary search")
assert_equal(
  true,
  bus.region_bytes("DICTIONARY").bytes.any?(&:nonzero?),
  "split-region dictionary bytes"
)

puts "PASS: Ruby outer interpreter tests completed"
