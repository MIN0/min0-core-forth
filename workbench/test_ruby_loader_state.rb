# frozen_string_literal: true

require_relative "loader_state_demo"

def loader_assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

result = run_loader_state_demo
loader_assert_equal("stable", result[:initial][:phase], "initial stable phase")
loader_assert_equal(
  {
    phase: "stable",
    runtime_profile: "safe-runtime",
    root_epoch: 3,
    minimum_root_epoch: 3,
    trust_epoch: 3,
    minimum_trust_epoch: 3,
    normal_generation: 2,
    minimum_normal_generation: 2,
    recovery_generation: 2,
    minimum_recovery_generation: 2,
    boot: {
      mode: "normal",
      slot: "B",
      generation: 2,
      sequence: 2,
      identity: "e1cd103c1561aff4e351cc7c75f4f8310a9a5985d59f3b28828422709ee6a4a6",
      trusted_generation: 2
    }
  },
  result[:final],
  "complete rotation state"
)
loader_assert_equal(
  [
    ["initialized", "stable"],
    ["stage-root", "root-awaiting-commit"],
    ["commit-root", "stable"],
    ["stage-trust", "trust-awaiting-commit"],
    ["commit-trust", "stable"],
    ["stage-normal", "normal-awaiting-commit"],
    ["commit-normal", "stable"],
    ["stage-recovery", "recovery-awaiting-commit"],
    ["commit-recovery", "stable"],
    ["stage-trust", "trust-awaiting-commit"],
    ["commit-trust", "stable"],
    ["stage-root", "root-awaiting-commit"],
    ["commit-root", "stable"]
  ],
  result[:history].map { |entry| [entry[:action], entry[:phase]] },
  "pending and commit history"
)
loader_assert_equal(true, result[:ordering].values.all?, "unsafe order rejection")
loader_assert_equal(true, result[:rejected].values.all?, "invalid package rejection")
loader_assert_equal(
  {
    "erase-inactive-root-state" => { root_epoch: 1, minimum_epoch: 1, phase: "stable" },
    "write-root-policy-chain" => { root_epoch: 1, minimum_epoch: 1, phase: "stable" },
    "seal-root-state" => { root_epoch: 2, minimum_epoch: 1, phase: "root-awaiting-commit" }
  },
  result[:root_stage_power_loss],
  "root stage power-loss matrix"
)
loader_assert_equal(
  {
    "erase-next-trusted-record" => { root_epoch: 2, minimum_epoch: 1, phase: "root-awaiting-commit" },
    "write-next-trusted-record" => { root_epoch: 2, minimum_epoch: 1, phase: "root-awaiting-commit" },
    "seal-next-trusted-record" => { root_epoch: 2, minimum_epoch: 2, phase: "stable" }
  },
  result[:root_commit_power_loss],
  "root commit power-loss matrix"
)

puts "PASS: Ruby loader-state tests completed"
