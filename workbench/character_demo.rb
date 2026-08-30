# frozen_string_literal: true

require "digest"
require "json"
require_relative "min0_core_forth_outer"

vm = Min0CoreForth::VM.new
dictionary = Min0CoreForth::RuntimeDictionary.new(vm)
Min0CoreForth.install_core_primitives(dictionary)
outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
outer.interpret("CREATE TEXT 0x46 C, 0x4F C, 0x52 C, 0x54 C, 0x48 C,")
text_entry = dictionary.find("TEXT")
outer.interpret(": FIRST TEXT C@ ;")
outer.interpret(": THIRD TEXT 2 CHARS + C@ ;")
outer.interpret(": TEXT-END TEXT 5 CHARS + ;")
outer.interpret(': COMPILED-TEXT S" Compiled" ;')
outer.interpret(': COMPILED-OUTPUT ." Service" ;')
stack = outer.interpret("TEXT FIRST THIRD TEXT-END")
vm.data_stack.clear
type_stack = outer.interpret("TEXT 5 TYPE")
quoted_stack = outer.interpret('S" Hello World" TYPE CR ." Done"')
compiled_stack = outer.interpret("COMPILED-TEXT")
outer.interpret("TYPE")
service_stack = outer.interpret("COMPILED-OUTPUT")
puts JSON.generate(
  {
    stack: stack,
    type_stack: type_stack,
    quoted_stack: quoted_stack,
    compiled_stack: compiled_stack,
    service_stack: service_stack,
    output: outer.output,
    terminal_text: outer.terminal_text,
    steps: vm.steps,
    text_address: text_entry.payload,
    text_hex: vm.memory.byteslice(text_entry.payload, 5).unpack1("H*"),
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
