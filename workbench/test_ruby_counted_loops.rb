# frozen_string_literal: true

require_relative "min0_core_forth_outer"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

def build_outer(max_loop_depth: 32)
  vm = Min0CoreForth::VM.new(max_loop_depth: max_loop_depth)
  dictionary = Min0CoreForth::RuntimeDictionary.new(vm)
  Min0CoreForth.install_core_primitives(dictionary)
  [vm, dictionary, Min0CoreForth::OuterInterpreter.new(vm, dictionary)]
end

vm, _dictionary, outer = build_outer
outer.interpret(": INDEXES 5 0 DO I LOOP ;")
assert_equal([0, 1, 2, 3, 4], outer.interpret("INDEXES"), "DO LOOP I")
assert_equal([], vm.loop_stack, "loop stack balanced")
assert_equal(
  "010500000001000000001517160b10000003",
  vm.memory.byteslice(0x1000, outer.code_here - 0x1000).unpack1("H*"),
  "DO LOOP code"
)

_vm, _dictionary, outer = build_outer
outer.interpret(": RANGE 5 2 DO I LOOP ;")
assert_equal([2, 3, 4], outer.interpret("RANGE"), "nonzero start")

vm, _dictionary, outer = build_outer
outer.interpret(": GRID 2 0 DO 3 0 DO I LOOP LOOP ;")
assert_equal([0, 1, 2, 0, 1, 2], outer.interpret("GRID"), "nested DO LOOP")
assert_equal([], vm.loop_stack, "nested loop stack balanced")

_vm, _dictionary, outer = build_outer
outer.interpret(": THREE 3 0 DO")
outer.interpret("I")
outer.interpret("LOOP ;")
assert_equal([0, 1, 2], outer.interpret("THREE"), "DO LOOP across inputs")

vm = Min0CoreForth::VM.new
program = [
  Min0CoreForth::Op::LIT, 2, 0, 0, 0,
  Min0CoreForth::Op::LIT, 0, 0, 0, 0,
  Min0CoreForth::Op::DO,
  Min0CoreForth::Op::UNLOOP,
  Min0CoreForth::Op::HALT
].pack("C*")
vm.load(program)
assert_equal([], vm.run, "UNLOOP execution")
assert_equal([], vm.loop_stack, "UNLOOP removes frame")

vm, _dictionary, outer = build_outer(max_loop_depth: 1)
outer.interpret(": NESTED 2 0 DO 2 0 DO I LOOP LOOP ;")
begin
  outer.interpret("NESTED")
  raise "nested limit: expected LoopStackOverflow"
rescue Min0CoreForth::LoopStackOverflow
  puts "nested loop limit: PASS"
  assert_equal([], vm.data_stack, "loop overflow data recovery")
  assert_equal([], vm.return_stack, "loop overflow return recovery")
  assert_equal([], vm.loop_stack, "loop overflow loop recovery")
end

[
  ": BAD DO ;",
  ": BAD LOOP ;",
  ": BAD DO IF LOOP THEN ;"
].each do |source|
  _vm, dictionary, outer = build_outer
  saved_here = dictionary.here
  saved_code_here = outer.code_here
  begin
    outer.interpret(source)
    raise "malformed DO LOOP: expected CompileStateError"
  rescue Min0CoreForth::CompileStateError
    assert_equal(Min0CoreForth::STATE_INTERPRET, outer.state, "DO LOOP rollback state")
    assert_equal([], outer.control_stack, "DO LOOP rollback control stack")
    assert_equal(saved_here, dictionary.here, "DO LOOP rollback dictionary")
    assert_equal(saved_code_here, outer.code_here, "DO LOOP rollback code")
    assert_equal(nil, dictionary.find("BAD", include_hidden: true), "DO LOOP rollback word")
  end
end

["DO", "LOOP"].each do |token|
  begin
    outer.interpret(token)
    raise "#{token}: expected CompileStateError"
  rescue Min0CoreForth::CompileStateError
    puts "#{token} compile-only: PASS"
  end
end

puts "PASS: Ruby counted-loop tests completed"
