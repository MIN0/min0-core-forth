# frozen_string_literal: true

require_relative "image_envelope_demo"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

result = run_image_envelope_demo
assert_equal(68, result[:record_count], "bound manifest count")
assert_equal(
  "b6752a2cbed614a7515f04722e5b9447aa0cc54bdcc5b5505acdee8dcbe8d694",
  result[:source_identity],
  "source identity"
)
assert_equal(true, result[:identity_changed], "linked identity changes")
assert_equal(false, result[:source_identity] == result[:different_identity], "different image identity")
assert_equal(7, result[:generation], "source generation")
assert_equal(7, result[:linked_generation], "linked generation preserved")

source = result[:source_allocator]
linked = result[:linked_allocator]
assert_equal(0x1000, linked["code_here"] - source["code_here"], "CODE-HERE relocation")
assert_equal(0x1000, linked["header_here"] - source["header_here"], "header HERE relocation")
assert_equal(0x1000, linked["data_here"] - source["data_here"], "data HERE relocation")
assert_equal(0x1000, linked["latest"] - source["latest"], "LATEST relocation")
assert_equal([99, 2, 3, 3, 0, 2, 7, 0x9000], result[:stack], "envelope linked execution")
assert_equal("none", result[:authentication], "explicit authentication state")
assert_equal(
  ["different-image", "different-envelope", "allocator-metadata", "manifest-digest", "authentication-required"],
  result[:rejected],
  "identity and policy rejections"
)

puts "PASS: Ruby image envelope tests completed"
