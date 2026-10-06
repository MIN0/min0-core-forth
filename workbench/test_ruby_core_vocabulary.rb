# frozen_string_literal: true

require_relative "min0_core_forth_outer"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

def build_core_host
  vm = Min0CoreForth::VM.new
  dictionary = Min0CoreForth::RuntimeDictionary.new(vm)
  Min0CoreForth.install_core_primitives(dictionary, extended: true)
  outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
  Min0CoreForth.install_core_vocabulary(outer)
  outer
end

outer = build_core_host
assert_equal([2, 3, 1], outer.interpret("1 2 3 ROT"), "ROT")

outer = build_core_host
assert_equal([1, 2, 1, 2], outer.interpret("1 2 2DUP"), "2DUP")

outer = build_core_host
assert_equal([0xFFFF_FFFF, 0xFFFF_FFFE], outer.interpret("-7 3 /MOD"), "signed /MOD")

outer = build_core_host
outer.interpret("1 2 -1 .S")
assert_equal("<3> 1 2 -1", outer.terminal_text, ".S output")
assert_equal([1, 2, 0xFFFF_FFFF], outer.vm.data_stack, ".S preserves stack")

outer = build_core_host
begin
  outer.interpret("7 0 /MOD")
  raise "division by zero: expected DivisionByZero"
rescue Min0CoreForth::DivisionByZero
  assert_equal([7, 0], outer.vm.data_stack, "division failure preserves stack")
end
