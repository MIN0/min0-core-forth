# frozen_string_literal: true

require_relative "min0_core_forth_outer"

def assert_compiled_output(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

def build_compiled_output_outer(max_data_depth: 256)
  vm = Min0CoreForth::VM.new(max_data_depth: max_data_depth)
  dictionary = Min0CoreForth::RuntimeDictionary.new(vm)
  Min0CoreForth.install_core_primitives(dictionary)
  Min0CoreForth::OuterInterpreter.new(vm, dictionary)
end

direct = build_compiled_output_outer
assert_compiled_output([], direct.interpret("65 EMIT CR -42 ."), "direct output stack")

compiled = build_compiled_output_outer
compiled.interpret(": OUTPUT 65 EMIT CR -42 . ;")
assert_compiled_output([], compiled.interpret("OUTPUT"), "compiled output stack")
assert_compiled_output(direct.output, compiled.output, "direct and compiled output")
assert_compiled_output("A\n-42", compiled.terminal_text, "compiled exact output")

outer = build_compiled_output_outer
outer.interpret(': SAY-ABC S" ABC" TYPE ;')
assert_compiled_output([], outer.interpret("SAY-ABC"), "compiled TYPE stack")
assert_compiled_output("ABC", outer.terminal_text, "compiled TYPE output")

outer = build_compiled_output_outer
outer.interpret(": DIGITS 3 FOR I 48 + EMIT NEXT ;")
assert_compiled_output([], outer.interpret("DIGITS"), "compiled loop EMIT stack")
assert_compiled_output("012", outer.terminal_text, "compiled loop EMIT output")

outer = build_compiled_output_outer
outer.interpret(": NEED-CHAR EMIT ;")
outer.interpret("65 EMIT")
begin
  outer.interpret("NEED-CHAR")
  raise "compiled EMIT underflow: expected StackUnderflow"
rescue Min0CoreForth::StackUnderflow
  assert_compiled_output([], outer.vm.data_stack, "compiled EMIT underflow stack")
  assert_compiled_output("A", outer.terminal_text, "compiled EMIT underflow output")
end

outer.interpret(": OUT-RANGE TYPE ;")
outer.vm.data_stack.replace([65_534, 4])
begin
  outer.interpret("OUT-RANGE")
  raise "compiled TYPE range: expected MemoryFault"
rescue Min0CoreForth::MemoryFault
  assert_compiled_output([65_534, 4], outer.vm.data_stack, "compiled TYPE fault stack")
  assert_compiled_output("A", outer.terminal_text, "compiled TYPE fault output")
end

outer = build_compiled_output_outer(max_data_depth: 1)
outer.interpret(": NEWLINE CR ;")
outer.interpret("7")
assert_compiled_output([7], outer.interpret("NEWLINE"), "compiled CR full stack")
assert_compiled_output("\n", outer.terminal_text, "compiled CR output")

puts "PASS: Ruby compiled output-word tests completed"
