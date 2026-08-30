# frozen_string_literal: true

require_relative "linker_validation_demo"
require_relative "full_image_relocation_demo"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

validation = run_linker_validation_demo
assert_equal(true, validation[:source_unchanged], "source components unchanged")
assert_equal(3, validation[:record_count], "synthetic manifest count")
assert_equal("0440000000600000efbeadde", validation[:code_hex], "linked CODE")
assert_equal("00400000", validation[:dictionary_hex], "linked DICTIONARY")
assert_equal("44332211", validation[:data_hex], "linked DATA")
assert_equal(
  ["version", "section", "width", "offset", "overlap", "pointer", "target-overlap", "overflow", "kind"],
  validation[:rejected],
  "transactional rejections"
)

full = run_full_image_relocation_demo
assert_equal(68, full[:manifest_records], "unified manifest count")
assert_equal(15, full[:code_relocations], "unified CODE records")
assert_equal(53, full[:dictionary_relocations], "unified DICTIONARY records")
assert_equal([99, 2, 3, 3, 0, 2, 7, 0x9000], full[:stack], "unified linked execution")

puts "PASS: Ruby transactional linker tests completed"
