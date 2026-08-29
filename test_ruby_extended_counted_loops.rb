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

vm, _dictionary, outer = build_outer
outer.interpret(": EVENS 10 0 DO I 2 +LOOP ;")
assert_equal([0, 2, 4, 6, 8], outer.interpret("EVENS"), "+LOOP positive")
vm.data_stack.clear
outer.interpret(": THREES 10 0 DO I 3 +LOOP ;")
assert_equal([0, 3, 6, 9], outer.interpret("THREES"), "+LOOP crossing")
assert_equal([], vm.loop_stack, "+LOOP stack balanced")

vm, _dictionary, outer = build_outer
outer.interpret(": DOWN -5 0 DO I -1 +LOOP ;")
assert_equal(
  [0, -1, -2, -3, -4],
  outer.interpret("DOWN").map { |value| Min0CoreForth.signed(value) },
  "+LOOP negative"
)
assert_equal([], vm.loop_stack, "negative +LOOP stack balanced")

assembler = Min0CoreForth::Assembler.new
assembler.emit(Min0CoreForth::Op::LIT, 5)
assembler.emit(Min0CoreForth::Op::LIT, 0)
assembler.emit(Min0CoreForth::Op::DO)
assembler.label("body")
assembler.emit(Min0CoreForth::Op::LIT, 0)
assembler.emit(Min0CoreForth::Op::PLOOP, "body")
assembler.emit(Min0CoreForth::Op::HALT)
vm = Min0CoreForth::VM.new
vm.load(assembler.build)
begin
  vm.run(max_steps: 20)
  raise "zero +LOOP: expected StepLimitExceeded"
rescue Min0CoreForth::StepLimitExceeded
  puts "zero +LOOP step limit: PASS"
end

vm, _dictionary, outer = build_outer
outer.interpret(": ZERO 0 0 ?DO I LOOP ;")
assert_equal([], outer.interpret("ZERO"), "?DO zero trip")
outer.interpret(": THREE 3 0 ?DO I LOOP ;")
assert_equal([0, 1, 2], outer.interpret("THREE"), "?DO normal trip")
assert_equal([], vm.loop_stack, "?DO loop stack balanced")

vm, _dictionary, outer = build_outer
outer.interpret(": PAIRS 2 0 DO 3 0 DO J I LOOP LOOP ;")
assert_equal(
  [0, 0, 0, 1, 0, 2, 1, 0, 1, 1, 1, 2],
  outer.interpret("PAIRS"),
  "J outer index"
)
assert_equal([], vm.loop_stack, "J loop stack balanced")

vm, _dictionary, outer = build_outer
begin
  outer.interpret("J")
  raise "J underflow: expected LoopStackUnderflow"
rescue Min0CoreForth::LoopStackUnderflow
  assert_equal([], vm.data_stack, "J underflow data recovery")
  assert_equal([], vm.return_stack, "J underflow return recovery")
  assert_equal([], vm.loop_stack, "J underflow loop recovery")
end

vm, _dictionary, outer = build_outer
outer.interpret(": STOP 10 0 DO I DUP 3 = IF LEAVE THEN LOOP ;")
assert_equal([0, 1, 2, 3], outer.interpret("STOP"), "LEAVE")
vm.data_stack.clear
outer.interpret(": INNERLEAVE 2 0 DO 5 0 DO I 1 = IF LEAVE THEN LOOP I LOOP ;")
assert_equal([0, 1], outer.interpret("INNERLEAVE"), "nested LEAVE")
assert_equal([], vm.loop_stack, "LEAVE loop stack balanced")

[
  ": BAD ?DO ;",
  ": BAD +LOOP ;",
  ": BAD LEAVE ;",
  ": BAD DO IF LEAVE THEN ;"
].each do |source|
  _vm, dictionary, outer = build_outer
  saved_here = dictionary.here
  saved_code_here = outer.code_here
  begin
    outer.interpret(source)
    raise "#{source}: expected CompileStateError"
  rescue Min0CoreForth::CompileStateError
    assert_equal(Min0CoreForth::STATE_INTERPRET, outer.state, "extended rollback state")
    assert_equal([], outer.control_stack, "extended rollback control stack")
    assert_equal(saved_here, dictionary.here, "extended rollback dictionary")
    assert_equal(saved_code_here, outer.code_here, "extended rollback code")
    assert_equal(nil, dictionary.find("BAD", include_hidden: true), "extended rollback word")
  end
end

["?DO", "+LOOP", "LEAVE"].each do |token|
  begin
    outer.interpret(token)
    raise "#{token}: expected CompileStateError"
  rescue Min0CoreForth::CompileStateError
    puts "#{token} compile-only: PASS"
  end
end

puts "PASS: Ruby extended counted-loop tests completed"
