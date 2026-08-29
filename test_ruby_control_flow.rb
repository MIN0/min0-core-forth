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
outer.interpret(": CHOOSE IF 111 ELSE 222 THEN ;")
assert_equal([222, 111], outer.interpret("0 CHOOSE 1 CHOOSE"), "IF ELSE THEN")
assert_equal(
  "050f100000016f000000041410000001de00000003",
  vm.memory.byteslice(0x1000, outer.code_here - 0x1000).unpack1("H*"),
  "patched branch bytes"
)

_vm, _dictionary, outer = build_outer
outer.interpret(": MAYBE IF 7 THEN ;")
assert_equal([7], outer.interpret("0 MAYBE 1 MAYBE"), "IF THEN")

_vm, _dictionary, outer = build_outer
outer.interpret(": NEST IF IF 1 ELSE 2 THEN ELSE 3 THEN ;")
assert_equal([3, 2, 1], outer.interpret("0 NEST 0 1 NEST 1 1 NEST"), "nested conditionals")

_vm, _dictionary, outer = build_outer
outer.interpret(": SPLIT IF 10")
outer.interpret("ELSE 20")
outer.interpret("THEN ;")
assert_equal([20, 10], outer.interpret("0 SPLIT 1 SPLIT"), "control flow across inputs")

_vm, dictionary, outer = build_outer
saved_dictionary_here = dictionary.here
saved_code_here = outer.code_here
begin
  outer.interpret(": BROKEN IF 1 ;")
  raise "unresolved IF: expected CompileStateError"
rescue Min0CoreForth::CompileStateError
  assert_equal(Min0CoreForth::STATE_INTERPRET, outer.state, "unresolved IF state rollback")
  assert_equal(saved_dictionary_here, dictionary.here, "unresolved IF dictionary rollback")
  assert_equal(saved_code_here, outer.code_here, "unresolved IF code rollback")
  assert_equal([], outer.control_stack, "unresolved IF control stack rollback")
  assert_equal(nil, dictionary.find("BROKEN", include_hidden: true), "unresolved IF word rollback")
end

["IF", "ELSE", "THEN"].each do |token|
  begin
    outer.interpret(token)
    raise "#{token}: expected CompileStateError"
  rescue Min0CoreForth::CompileStateError
    puts "#{token} compile-only: PASS"
  end
end

begin
  outer.interpret(": BAD ELSE ;")
  raise "mismatched ELSE: expected CompileStateError"
rescue Min0CoreForth::CompileStateError
  assert_equal(nil, dictionary.find("BAD", include_hidden: true), "mismatched ELSE rollback")
end

puts "PASS: Ruby control-flow tests completed"
