# frozen_string_literal: true

require "digest"
require "json"
require_relative "min0_core_forth_outer"

vm = Min0CoreForth::VM.new
dictionary = Min0CoreForth::RuntimeDictionary.new(vm)
Min0CoreForth.install_core_primitives(dictionary)
outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
outer.interpret(": EVENS 10 0 DO I 2 +LOOP ;")
outer.interpret(": DOWN -5 0 DO I -1 +LOOP ;")
outer.interpret(": ZERO 0 0 ?DO I LOOP ;")
outer.interpret(": PAIRS 2 0 DO 3 0 DO J I LOOP LOOP ;")
outer.interpret(": STOP 10 0 DO I DUP 3 = IF LEAVE THEN LOOP ;")
stack = outer.interpret("EVENS DOWN ZERO PAIRS STOP")
puts JSON.generate(
  {
    stack: stack,
    steps: vm.steps,
    code_here: outer.code_here,
    code_hex: vm.memory.byteslice(0x1000, outer.code_here - 0x1000).unpack1("H*"),
    dictionary_sha256: Digest::SHA256.hexdigest(dictionary.image),
    state: outer.state,
    control_depth: outer.control_stack.length,
    return_depth: vm.return_stack.length,
    loop_depth: vm.loop_stack.length,
    max_depths: [vm.max_data_depth, vm.max_return_depth, vm.max_loop_depth]
  }
)
