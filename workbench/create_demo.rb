# frozen_string_literal: true

require "digest"
require "json"
require_relative "min0_core_forth_outer"

vm = Min0CoreForth::VM.new
dictionary = Min0CoreForth::RuntimeDictionary.new(vm)
Min0CoreForth.install_core_primitives(dictionary)
outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
outer.interpret("CREATE TABLE 10 , 20 ,")
outer.interpret("CREATE BUFFER 3 CELLS ALLOT")
table = dictionary.find("TABLE")
buffer = dictionary.find("BUFFER")
outer.interpret(": TOTAL TABLE @ TABLE CELL+ @ + ;")
outer.interpret(": BUFFER-END BUFFER 3 CELLS + ;")
stack = outer.interpret("TABLE TOTAL BUFFER BUFFER-END")
puts JSON.generate(
  {
    stack: stack,
    steps: vm.steps,
    table: [table.kind, table.payload, vm.read_cell(table.payload), vm.read_cell(table.payload + 4)],
    buffer: [buffer.kind, buffer.payload, dictionary.find("BUFFER").payload],
    final_here: dictionary.here,
    latest: dictionary.latest,
    code_here: outer.code_here,
    code_hex: vm.memory.byteslice(0x1000, outer.code_here - 0x1000).unpack1("H*"),
    dictionary_sha256: Digest::SHA256.hexdigest(dictionary.image),
    state: outer.state,
    return_depth: vm.return_stack.length,
    loop_depth: vm.loop_stack.length
  }
)
