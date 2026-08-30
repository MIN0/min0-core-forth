# frozen_string_literal: true

require "digest"
require "json"
require_relative "min0_core_forth_outer"

vm = Min0CoreForth::VM.new
dictionary = Min0CoreForth::RuntimeDictionary.new(vm)
Min0CoreForth.install_core_primitives(dictionary)
outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
outer.interpret(": INDEXES 5 0 DO I LOOP ;")
outer.interpret(": GRID 2 0 DO 3 0 DO I LOOP LOOP ;")
stack = outer.interpret("INDEXES GRID")
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
