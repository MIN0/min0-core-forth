# frozen_string_literal: true

require_relative "code_relocation_demo"
require_relative "full_image_relocation_demo"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

result = run_code_relocation_demo
assert_equal(15, result[:manifest].length, "manifest count")
assert_equal(
  {
    "branch" => 2,
    "call" => 2,
    "data-literal" => 1,
    "does-body" => 1,
    "does-call" => 1,
    "leave" => 1,
    "loop" => 2,
    "ploop" => 1,
    "qdo" => 1,
    "zbranch" => 3
  },
  result[:kind_counts],
  "manifest kinds"
)
assert_equal(
  { "code" => 13, "dictionary" => 0, "data" => 2 },
  result[:target_counts],
  "manifest targets"
)
assert_equal(
  [99, 2, 3, 3, 0, 2, 7, 0x8000],
  result[:stack],
  "compiled execution"
)
assert_equal(true, result[:manifest].all? { |record| record[:section] == "code" }, "CODE section")
assert_equal(true, result[:manifest].all? { |record| record[:width] == 4 }, "Reference32 width")

vm, dictionary = make_image_system
Min0CoreForth.install_core_primitives(dictionary)
outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
outer.interpret(": GOOD IF 1 THEN ;")
before = outer.relocation_manifest
begin
  outer.interpret(": BAD IF ;")
  raise "failed definition was accepted"
rescue Min0CoreForth::CompileStateError
  # Expected.
end
assert_equal(before, outer.relocation_manifest, "failed definition manifest rollback")

full = run_full_image_relocation_demo
assert_equal(15, full[:code_relocations], "full image CODE relocations")
assert_equal(53, full[:dictionary_relocations], "full image DICTIONARY relocations")
assert_equal(
  { "code" => 12, "dictionary" => 39, "data" => 2 },
  full[:dictionary_targets],
  "full image DICTIONARY targets"
)
assert_equal([99, 2, 3, 3, 0, 2, 7, 0x9000], full[:stack], "full image execution")
assert_equal(0x9000, full[:slot], "relocated SLOT")
assert_equal(0x9004, full[:answer_body], "relocated ANSWER body")
assert_equal(7, full[:answer_value], "relocated ANSWER value")
assert_equal(0x9008, full[:data_here], "relocated data HERE")

puts "PASS: Ruby compiler relocation tests completed"
