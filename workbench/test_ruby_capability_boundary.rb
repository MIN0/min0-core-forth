# frozen_string_literal: true

require_relative "capability_boundary_demo"

def capability_assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

result = run_capability_boundary_demo
capability_assert_equal(
  {
    runtime: ["inspect"],
    monitor: %w[inspect normal],
    recovery: ["inspect", "normal-in-recovery-mode"],
    provisioner: %w[inspect normal recovery trust root]
  },
  result[:permissions],
  "least-privilege profiles"
)
capability_assert_equal(true, result[:readable].values.all?, "read access")
capability_assert_equal(true, result[:denied].values.all?, "unauthorized access rejection")
capability_assert_equal(
  {
    owner_visible: { label: "update-monitor", domain: "normal", slot: "B" },
    normal_slot: "B",
    phase_after_commit: "stable"
  },
  result[:ownership],
  "transaction ownership"
)
capability_assert_equal(
  { slot: "B", mode_after_stage: "normal", final_mode: "normal", generation: 2 },
  result[:recovery_repair],
  "recovery-only normal repair"
)
capability_assert_equal(
  {
    phase: "normal-awaiting-commit",
    domain: "normal",
    slot: "B",
    final_phase: "stable",
    generation: 2
  },
  result[:restart_adoption],
  "authorized restart adoption"
)

puts "PASS: Ruby capability-boundary tests completed"
