# frozen_string_literal: true

require_relative "trust_rotation_demo"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

result = run_trust_rotation_demo
assert_equal(1, result[:bundle_format_version], "trust bundle version")
assert_equal(
  "d404bc44565aedbb899150e5b0b3b32b9441bf0cb7884c33130da8dbc27dd2cf",
  result[:root_public_key_hex],
  "root public key vector"
)
assert_equal(
  {
    "erase-inactive-trust-slot" => { visible_epoch: 1, minimum_epoch: 1 },
    "write-trust-bundle" => { visible_epoch: 1, minimum_epoch: 1 },
    "seal-trust-slot" => { visible_epoch: 2, minimum_epoch: 1 }
  },
  result[:bundle_power_loss],
  "trust bundle power-loss matrix"
)
assert_equal(
  {
    "erase-next-trusted-record" => { visible_epoch: 2, minimum_epoch: 1 },
    "write-next-trusted-record" => { visible_epoch: 2, minimum_epoch: 1 },
    "seal-next-trusted-record" => { visible_epoch: 2, minimum_epoch: 2 }
  },
  result[:epoch_commit_power_loss],
  "trust epoch power-loss matrix"
)
assert_equal(
  { overlap_accepts_old_and_new: true, old_revoked_at_epoch3: true, new_survives_epoch3: true },
  result[:normal_rotation],
  "normal key overlap and revocation"
)
result[:recovery_update_power_loss].to_a[0...-1].each do |step, state|
  assert_equal(1, state[:generation], "#{step} keeps recovery generation 1")
  assert_equal("A", state[:slot], "#{step} keeps recovery A")
end
assert_equal(
  2,
  result[:recovery_update_power_loss]["seal-complete-marker"][:generation],
  "sealed recovery generation 2"
)
assert_equal(2, result[:post_revoke_recovery_boot][:generation], "new recovery survives revocation")
assert_equal(
  { premature_revoke_breaks_old_recovery: true, correct_order_keeps_new_recovery: true },
  result[:ordering],
  "recovery rotation ordering"
)
assert_equal(
  { bundle_rollback: true, forged_root_signature: true, tampered_bundle: true },
  result[:rejected],
  "trust attack rejection matrix"
)
assert_equal(4, result[:final_trust_epoch], "final trust epoch")

puts "PASS: Ruby trust rotation tests completed"
