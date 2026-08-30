# frozen_string_literal: true

require_relative "root_rotation_demo"

def root_assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

result = run_root_rotation_demo
root_assert_equal(1, result[:root_policy_format_version], "root policy version")
root_assert_equal(
  {
    old: "d404bc44565aedbb899150e5b0b3b32b9441bf0cb7884c33130da8dbc27dd2cf",
    new: "ed3234b276d4ceda57d59bad14fbaf5a773c0f318c999de3a60d53c5a5b34c05"
  },
  result[:root_public_keys],
  "root public key vectors"
)
root_assert_equal(
  {
    "erase-inactive-root-state" => { visible_epoch: 1, minimum_epoch: 1 },
    "write-root-policy-chain" => { visible_epoch: 1, minimum_epoch: 1 },
    "seal-root-state" => { visible_epoch: 2, minimum_epoch: 1 }
  },
  result[:root_write_power_loss],
  "root-state power-loss matrix"
)
root_assert_equal(
  {
    "erase-next-trusted-record" => { visible_epoch: 2, minimum_epoch: 1 },
    "write-next-trusted-record" => { visible_epoch: 2, minimum_epoch: 1 },
    "seal-next-trusted-record" => { visible_epoch: 2, minimum_epoch: 2 }
  },
  result[:root_commit_power_loss],
  "root-epoch power-loss matrix"
)
root_assert_equal(
  {
    overlap_accepts_old_and_new_bundles: true,
    new_bundle_survives_retirement: true,
    old_bundle_rejected_after_retirement: true,
    premature_retirement_breaks_old_bundle: true,
    post_retirement_new_root_only_policy: true
  },
  result[:ordering],
  "safe root rotation order"
)
root_assert_equal(
  {
    missing_new_signature: true,
    tampered_signature: true,
    broken_chain_link: true,
    root_key_replacement: true,
    retired_root_reactivation: true,
    root_policy_rollback: true,
    corrupted_committed_chain_fails_closed: true
  },
  result[:rejected],
  "root policy attack rejection matrix"
)
root_assert_equal(4, result[:final_root_epoch], "final root epoch")
root_assert_equal(
  [ROOT_ROTATE_NEW_ID], result[:final_active_roots], "final active root"
)

puts "PASS: Ruby root rotation tests completed"
