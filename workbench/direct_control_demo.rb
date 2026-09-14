# frozen_string_literal: true

require "json"
require_relative "min0_core_forth_outer"

vm = Min0CoreForth::VM.new
dictionary = Min0CoreForth::RuntimeDictionary.new(vm)
Min0CoreForth.install_core_primitives(dictionary)
outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
outer.interpret("1 IF 10 ELSE 20 THEN")
outer.interpret("0 BEGIN 1 + DUP 3 = UNTIL")
outer.interpret("5 2 DO I LOOP")
outer.interpret("2 FOR I DUP 0 = IF 8 ELSE 9 THEN NEXT")
puts JSON.generate(
  {
    stack: vm.data_stack,
    output: outer.terminal_text,
    state: outer.state,
    loop_depth: vm.loop_stack.length
  }
)
