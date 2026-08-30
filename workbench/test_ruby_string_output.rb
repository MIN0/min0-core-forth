# frozen_string_literal: true

require_relative "min0_core_forth_outer"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

def build_string_outer(limit: nil, install_primitives: true, max_data_depth: 256)
  vm = Min0CoreForth::VM.new(max_data_depth: max_data_depth)
  dictionary = Min0CoreForth::RuntimeDictionary.new(vm, limit: limit)
  Min0CoreForth.install_core_primitives(dictionary) if install_primitives
  [vm, dictionary, Min0CoreForth::OuterInterpreter.new(vm, dictionary)]
end

tokens = Min0CoreForth::Compiler.tokenize(%Q{1 s" MiXeD  \\ text" ." done" \\ outside\n2})
assert_equal(
  [
    "1",
    Min0CoreForth::QuotedText.new('S"', "MiXeD  \\ text"),
    Min0CoreForth::QuotedText.new('."', "done"),
    "2"
  ],
  tokens,
  "quoted tokenizer"
)

vm, dictionary, outer = build_string_outer
before = dictionary.data_here
assert_equal([before, 12], outer.interpret('S" Hello  World"'), "S-quote stack")
assert_equal("Hello  World".b, vm.read_bytes(before, 12), "S-quote bytes")
assert_equal([], outer.interpret("TYPE"), "S-quote TYPE stack")
assert_equal(["Hello  World"], outer.output, "S-quote TYPE output")

_vm, dictionary, outer = build_string_outer
before = dictionary.data_here
assert_equal([], outer.interpret('." MiXeD Case"'), "dot-quote stack")
assert_equal(["MiXeD Case"], outer.output, "dot-quote output")
assert_equal(before, dictionary.data_here, "dot-quote no allocation")

vm, dictionary, outer = build_string_outer
before = dictionary.data_here
assert_equal([before, 0], outer.interpret('S""'), "empty S-quote")
assert_equal(before, dictionary.data_here, "empty S-quote HERE")
assert_equal([], outer.interpret("TYPE"), "empty TYPE stack")
assert_equal([], outer.output, "empty TYPE output")
assert_equal([before, 4], outer.interpret('S" café"'), "Latin-1 S-quote")
assert_equal("caf\xE9".b, vm.read_bytes(before, 4), "Latin-1 bytes")
assert_equal([], outer.interpret("TYPE"), "Latin-1 TYPE stack")
assert_equal("café", outer.terminal_text, "Latin-1 exact output")

_vm, _dictionary, outer = build_string_outer
outer.interpret(%Q{." A\\B" \\ ignored\n ." C"})
assert_equal(["A\\B", "C"], outer.output, "quoted backslash")

vm, dictionary, outer = build_string_outer
before = dictionary.data_here
begin
  outer.interpret('65 EMIT ." missing')
  raise "unterminated string: expected CompileError"
rescue Min0CoreForth::CompileError
  assert_equal([], vm.data_stack, "unterminated stack")
  assert_equal([], outer.output, "unterminated output")
  assert_equal(before, dictionary.data_here, "unterminated HERE")
end
begin
  outer.interpret('S" Ā"')
  raise "nonbyte string: expected CompileStateError"
rescue Min0CoreForth::CompileStateError
  assert_equal([], vm.data_stack, "nonbyte stack")
  assert_equal([], outer.output, "nonbyte output")
  assert_equal(before, dictionary.data_here, "nonbyte HERE")
end

vm, dictionary, outer = build_string_outer(
  limit: Min0CoreForth::DICTIONARY_BASE + 1, install_primitives: false
)
before = dictionary.data_here
begin
  outer.interpret('S" AB"')
  raise "full S-quote: expected DictionaryFull"
rescue Min0CoreForth::DictionaryFull
  assert_equal([], vm.data_stack, "full S-quote stack")
  assert_equal(before, dictionary.data_here, "full S-quote HERE")
end

vm, dictionary, outer = build_string_outer(max_data_depth: 1)
before = dictionary.data_here
begin
  outer.interpret('S" A"')
  raise "S-quote stack capacity: expected DataStackOverflow"
rescue Min0CoreForth::DataStackOverflow
  assert_equal([], vm.data_stack, "S-quote overflow stack")
  assert_equal(before, dictionary.data_here, "S-quote overflow HERE")
end

vm, dictionary, outer = build_string_outer
outer.interpret(': MESSAGE S" Compiled" ;')
stack = outer.interpret("MESSAGE")
assert_equal(8, stack[-1], "compiled S-quote length")
assert_equal("Compiled".b, vm.read_bytes(stack[-2], stack[-1]), "compiled S-quote bytes")
assert_equal([], outer.interpret("TYPE"), "compiled S-quote TYPE stack")
assert_equal("Compiled", outer.terminal_text, "compiled S-quote output")
record = outer.relocation_manifest[-1]
assert_equal("data", record[:target], "compiled S-quote relocation target")
assert_equal("string-address", record[:kind], "compiled S-quote relocation kind")

vm, dictionary, outer = build_string_outer
outer.interpret(': STRINGS S" A" S" BC" S"" ;')
stack = outer.interpret("STRINGS")
assert_equal([1, 2, 0], [stack[1], stack[3], stack[5]], "multiple S-quote lengths")
assert_equal("A".b, vm.read_bytes(stack[0], 1), "first compiled string")
assert_equal("BC".b, vm.read_bytes(stack[2], 2), "second compiled string")
assert_equal(dictionary.body_base, stack[4], "empty compiled string address")
assert_equal(
  ["string-address", "string-address", "string-address"],
  outer.relocation_manifest.last(3).map { |item| item[:kind] },
  "multiple S-quote relocations"
)

_vm, _dictionary, outer = build_string_outer
outer.interpret(': HELLO ." Hello" ;')
outer.interpret(': GREET HELLO ."  World" ."" ;')
assert_equal([], outer.interpret("GREET"), "compiled dot-quote stack")
assert_equal(["Hello", " World"], outer.output, "compiled dot-quote fragments")
assert_equal("Hello World", outer.terminal_text, "compiled dot-quote exact output")
records = outer.relocation_manifest.select { |item| item[:kind] == "string-address" }
assert_equal(3, records.length, "compiled dot-quote relocation count")
assert_equal(true, records.all? { |item| item[:target] == "data" }, "compiled dot-quote targets")

vm, dictionary, outer = build_string_outer
before_here = dictionary.here
before_code = outer.code_here
before_manifest = outer.relocation_manifest
[
  ': BAD S" text" MISSING ;',
  ': BAD ." text" MISSING ;',
  ': BAD S" Ā" ;',
  ': BAD ." Ā" ;'
].each do |source|
  begin
    outer.interpret(source)
    raise "compiled string failure: expected error"
  rescue Min0CoreForth::OuterInterpreterError, Min0CoreForth::CompileStateError
    assert_equal(nil, dictionary.find("BAD"), "compiled quoted rollback word")
    assert_equal(before_here, dictionary.here, "compiled quoted rollback HERE")
    assert_equal(before_code, outer.code_here, "compiled quoted rollback CODE")
    assert_equal(before_manifest, outer.relocation_manifest, "compiled quoted rollback manifest")
    assert_equal("\x00" * 8, vm.read_bytes(before_here, 8), "compiled quoted rollback bytes")
  end
end

['S" text"', '." text"', ': BAD S" text" ;'].each do |source|
  begin
    Min0CoreForth::Compiler.compile(source)
    raise "raw compiler quoted word: expected CompileError"
  rescue Min0CoreForth::CompileError
    puts "raw compiler rejects #{source}: PASS"
  end
end

puts "PASS: Ruby string-output tests completed"
