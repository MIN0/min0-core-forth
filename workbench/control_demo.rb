# frozen_string_literal: true

require "digest"
require "json"
require_relative "min0_core_forth_outer"

vm = Min0CoreForth::VM.new
dictionary = Min0CoreForth::RuntimeDictionary.new(vm)
Min0CoreForth.install_core_primitives(dictionary)
outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
outer.interpret(": CHOOSE IF 111 ELSE 222 THEN ;")
stack = outer.interpret("0 CHOOSE 1 CHOOSE")
puts JSON.generate(
  {
    stack: stack,
    steps: vm.steps,
    code_here: outer.code_here,
    code_hex: vm.memory.byteslice(0x1000, outer.code_here - 0x1000).unpack1("H*"),
    dictionary_sha256: Digest::SHA256.hexdigest(dictionary.image),
    state: outer.state,
    control_depth: outer.control_stack.length
  }
)
