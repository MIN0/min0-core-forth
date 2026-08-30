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
  [vm, dictionary, Min0CoreForth::OuterInterpreter.new(vm, dictionary)]
end

_vm, _dictionary, outer = build_outer
outer.interpret(": COUNTDOWN BEGIN 1 - DUP 0 = UNTIL ;")
assert_equal([0], outer.interpret("3 COUNTDOWN"), "BEGIN UNTIL")

_vm, _dictionary, outer = build_outer
outer.interpret(": DOWN BEGIN 0 OVER < WHILE 1 - REPEAT ;")
assert_equal([0], outer.interpret("4 DOWN"), "BEGIN WHILE REPEAT")

vm, dictionary, outer = build_outer
outer.interpret(": FOREVER BEGIN 1 AGAIN ;")
forever = dictionary.find("FOREVER")
assert_equal(
  "0101000000040010000003",
  vm.memory.byteslice(0x1000, outer.code_here - 0x1000).unpack1("H*"),
  "BEGIN AGAIN code"
)
begin
  vm.resume(forever.payload, return_to: outer.return_trampoline, max_steps: 20)
  raise "step limit: expected StepLimitExceeded"
rescue Min0CoreForth::StepLimitExceeded
  puts "BEGIN AGAIN step limit: PASS"
end

_vm, _dictionary, outer = build_outer
outer.interpret(": WALK BEGIN DUP 2 = IF 2 - ELSE 1 - THEN DUP 0 = UNTIL ;")
assert_equal([0], outer.interpret("3 WALK"), "IF nested inside loop")

_vm, _dictionary, outer = build_outer
outer.interpret(": DOWN BEGIN")
outer.interpret("0 OVER < WHILE")
outer.interpret("1 - REPEAT ;")
assert_equal([0], outer.interpret("2 DOWN"), "loop across input calls")

malformed = [
  ": BAD UNTIL ;",
  ": BAD AGAIN ;",
  ": BAD WHILE ;",
  ": BAD REPEAT ;",
  ": BAD BEGIN ;",
  ": BAD BEGIN WHILE 1 UNTIL ;",
  ": BAD BEGIN REPEAT ;"
]
malformed.each do |source|
  _vm, dictionary, outer = build_outer
  saved_dictionary_here = dictionary.here
  saved_code_here = outer.code_here
  begin
    outer.interpret(source)
    raise "malformed loop: expected CompileStateError for #{source.inspect}"
  rescue Min0CoreForth::CompileStateError
    assert_equal(Min0CoreForth::STATE_INTERPRET, outer.state, "malformed loop state")
    assert_equal([], outer.control_stack, "malformed loop control stack")
    assert_equal(saved_dictionary_here, dictionary.here, "malformed loop dictionary rollback")
    assert_equal(saved_code_here, outer.code_here, "malformed loop code rollback")
    assert_equal(nil, dictionary.find("BAD", include_hidden: true), "malformed loop word rollback")
  end
end

["BEGIN", "UNTIL", "AGAIN", "WHILE", "REPEAT"].each do |token|
  begin
    outer.interpret(token)
    raise "#{token}: expected CompileStateError"
  rescue Min0CoreForth::CompileStateError
    puts "#{token} compile-only: PASS"
  end
end

puts "PASS: Ruby loop tests completed"
