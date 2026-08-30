# frozen_string_literal: true

require_relative "anti_rollback_demo"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

result = run_anti_rollback_demo
assert_equal(
  { old: true, current: true, next: true },
  result[:signature_valid],
  "all signatures valid"
)
assert_equal(true, result[:old_signed_image_rejected], "signed old image rejected")
assert_equal(
  { before_failed_install: 7, after_failed_install: 7, after_successful_install: 8 },
  result[:trusted_state],
  "commit-after-success state"
)
assert_equal(true, result[:current_rejected_after_commit], "previous generation rejected")
assert_equal(8, result[:linked_generation], "generation survives relocation")
assert_equal(
  { negative_rejected: true, overflow_rejected: true, lower_commit_rejected: true },
  result[:bounds],
  "uint64 bounds and monotonic state"
)
assert_equal(5, result[:format_version], "image envelope v5")

puts "PASS: Ruby anti-rollback tests completed"
