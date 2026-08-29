# frozen_string_literal: true

require "digest"
require "json"
require_relative "min0_core_forth_outer"

vm = Min0CoreForth::VM.new
dictionary = Min0CoreForth::RuntimeDictionary.new(vm)
Min0CoreForth.install_core_primitives(dictionary)
outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
start_here = dictionary.here
outer.interpret("3 ALLOT")
comma_address = (dictionary.here + 3) & ~3
outer.interpret("0x12345678 ,")
outer.interpret("123 CONSTANT ANSWER")
outer.interpret("VARIABLE SLOT")
constant_entry = dictionary.find("ANSWER")
variable_entry = dictionary.find("SLOT")
outer.interpret(": USE ANSWER SLOT ! SLOT @ ;")
stack = outer.interpret("HERE USE")
puts JSON.generate(
  {
    stack: stack,
    steps: vm.steps,
    start_here: start_here,
    final_here: dictionary.here,
    latest: dictionary.latest,
    comma_address: comma_address,
    comma_value: vm.read_cell(comma_address),
    constant: [constant_entry.kind, constant_entry.payload],
    variable: [variable_entry.kind, variable_entry.payload, vm.read_cell(variable_entry.payload)],
    code_here: outer.code_here,
    code_hex: vm.memory.byteslice(0x1000, outer.code_here - 0x1000).unpack1("H*"),
    dictionary_sha256: Digest::SHA256.hexdigest(dictionary.image),
    state: outer.state,
    return_depth: vm.return_stack.length,
    loop_depth: vm.loop_stack.length
  }
)
