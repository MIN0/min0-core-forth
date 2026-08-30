# frozen_string_literal: true

require "json"
require "digest"
require_relative "min0_core_forth_outer"

vm = Min0CoreForth::VM.new
dictionary = Min0CoreForth::RuntimeDictionary.new(vm)
Min0CoreForth.install_core_primitives(dictionary)
outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
outer.interpret(": SQUARE DUP * ; : DOUBLE DUP + ;")
result = outer.interpret("5 SQUARE 7 DOUBLE")
outer.interpret("65 EMIT 66 EMIT CR 0x141 EMIT 0x1FF EMIT")
outer.interpret("WORDS")
puts JSON.generate(
  {
    stack: result,
    steps: vm.steps,
    return_depth: vm.return_stack.length,
    here: dictionary.here,
    latest: dictionary.latest,
    code_here: outer.code_here,
    code_hex: vm.memory.byteslice(0x1000, outer.code_here - 0x1000).unpack1("H*"),
    dictionary_sha256: Digest::SHA256.hexdigest(dictionary.image),
    state: outer.state,
    output: outer.output,
    terminal_text: outer.terminal_text
  }
)
