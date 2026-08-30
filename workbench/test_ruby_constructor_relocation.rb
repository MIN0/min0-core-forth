# frozen_string_literal: true

require_relative "constructor_relocation_demo"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

result = run_relocation_demo
assert_equal([0x1000, 0x4000, 0x8000], result[:source_bases], "source bases")
assert_equal([0x2000, 0x5000, 0x9000], result[:moved_bases], "moved bases")
assert_equal([0x1000, 0x1000, 0x1000], result[:deltas], "region deltas")
assert_equal(31, result[:relocation_count], "relocation count")
assert_equal(
  { "code" => 4, "dictionary" => 27, "data" => 0 },
  result[:target_counts],
  "relocation targets"
)
assert_equal(
  "bffe20da07aaba7b392fb6a299eafe3e5723a204dba547e43902151fe318a452",
  result[:manifest_sha256],
  "manifest digest"
)
assert_equal([2, 3, 4, 0], result[:actions], "RECORD actions")
assert_equal([0x9000], result[:stack], "relocated ITEM stack")
assert_equal(0x9000, result[:item_body], "relocated ITEM body")
assert_equal("ab000000", result[:body_hex], "relocated ITEM bytes")
assert_equal(0x9004, result[:data_here], "relocated data HERE")

puts "PASS: Ruby typed constructor-metadata relocation tests completed"
