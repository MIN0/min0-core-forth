# frozen_string_literal: true

require_relative "transactional_install_demo"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

result = run_transactional_install_demo
result[:install_steps][0...-1].each do |step|
  assert_equal(
    { boot_generation: 7, boot_slot: "A", trusted_generation: 7 },
    result[:install_power_loss][step],
    "unsealed #{step} keeps A"
  )
end
assert_equal(
  { boot_generation: 8, boot_slot: "B", trusted_generation: 7 },
  result[:install_power_loss]["seal-complete-marker"],
  "sealed marker exposes B"
)
result[:trust_commit_steps][0, 2].each do |step|
  assert_equal(8, result[:trust_power_loss][step][:boot_generation], "#{step} boots B")
  assert_equal(7, result[:trust_power_loss][step][:trusted_generation], "#{step} keeps trusted 7")
end
assert_equal(
  { boot_generation: 8, boot_slot: "B", trusted_generation: 8 },
  result[:trust_power_loss]["seal-next-trusted-record"],
  "sealed trusted record advances to 8"
)
assert_equal(8, result[:successful_commit_generation], "successful boot commits generation")
%i[failed_boot_fallback corrupted_candidate_fallback torn_marker_fallback unchanged_after_rollback].each do |name|
  assert_equal(7, result[name][:generation], "#{name} generation")
  assert_equal("A", result[name][:slot], "#{name} slot")
end
assert_equal(true, result[:rollback_rejected], "rollback rejected before mutation")
assert_equal(
  { fallback_generation: 7, boot_generation: 8 },
  result[:trusted_journal_corruption],
  "trusted journal corruption fallback"
)
assert_equal(
  true,
  result[:post_commit_active_corruption_requires_recovery],
  "post-commit corruption exposes recovery boundary"
)

puts "PASS: Ruby transactional install tests completed"
