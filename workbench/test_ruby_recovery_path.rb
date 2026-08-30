# frozen_string_literal: true

require_relative "recovery_path_demo"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

result = run_recovery_path_demo
assert_equal(5, result[:format_version], "image envelope v5")
assert_equal("recovery", result[:recovery_role], "recovery role")
assert_equal("recovery", result[:recovery_boot][:mode], "recovery boot mode")
assert_equal("R", result[:recovery_boot][:slot], "protected recovery slot")
assert_equal({ normal: 8, recovery: 1 }, result[:separate_generations], "separate generation domains")
result[:repair_steps][0...-1].each do |step|
  assert_equal(
    { mode: "recovery", generation: 1, normal_trusted_generation: 8 },
    result[:repair_power_loss][step],
    "#{step} remains in recovery"
  )
end
assert_equal(
  { mode: "normal", generation: 8, normal_trusted_generation: 8 },
  result[:repair_power_loss]["seal-complete-marker"],
  "sealed repair returns to normal"
)
assert_equal("normal", result[:repaired_boot][:mode], "completed repair mode")
assert_equal(8, result[:repaired_boot][:generation], "completed repair generation")
assert_equal(8, result[:normal_trusted_after_repair], "repair does not lower trusted generation")
assert_equal(
  {
    old_normal_repair: true,
    normal_as_recovery: true,
    recovery_as_normal: true,
    role_tamper: true,
    repair_outside_recovery: true
  },
  result[:rejected],
  "role and authorization rejection matrix"
)
assert_equal(true, result[:corrupt_recovery_total_failure_visible], "corrupt recovery is explicit failure")

puts "PASS: Ruby recovery path tests completed"
