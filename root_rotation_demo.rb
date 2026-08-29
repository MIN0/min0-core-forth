# frozen_string_literal: true

require "json"
require_relative "min0_core_forth_root"
require_relative "min0_core_forth_trust"
require_relative "auth_comparison_demo"

ROOT_ROTATE_OLD_ID = "fixture-offline-root-01"
ROOT_ROTATE_NEW_ID = "fixture-offline-root-02"
# Public, deterministic test fixtures only. Never use these keys in deployment.
ROOT_ROTATE_OLD_TEST_SEED = ([0xC3] * 32).pack("C*").freeze
ROOT_ROTATE_NEW_TEST_SEED = ([0xD4] * 32).pack("C*").freeze
ROOT_ROTATE_IMAGE_ID = "fixture-ed25519-01"

def root_rotation_entry(key_id, public_key, status)
  { key_id: key_id, public_key_hex: public_key.unpack1("H*"), status: status }
end

def root_rotation_image_entry(public_key)
  {
    key_id: ROOT_ROTATE_IMAGE_ID,
    role: Min0CoreForth::IMAGE_ROLE_NORMAL,
    public_key_hex: public_key.unpack1("H*"),
    status: "active"
  }
end

def root_rotation_rejected(*errors)
  yield
  false
rescue *errors
  true
end

def run_root_rotation_demo(implementation = "ruby")
  old_private = Min0CoreForth::Authentication.ed25519_private_from_seed(ROOT_ROTATE_OLD_TEST_SEED)
  new_private = Min0CoreForth::Authentication.ed25519_private_from_seed(ROOT_ROTATE_NEW_TEST_SEED)
  old_public = Min0CoreForth::Authentication.ed25519_public_bytes(old_private)
  new_public = Min0CoreForth::Authentication.ed25519_public_bytes(new_private)
  pinned = { ROOT_ROTATE_OLD_ID => old_public }

  roots1 = [root_rotation_entry(ROOT_ROTATE_OLD_ID, old_public, "active")]
  roots2 = [
    root_rotation_entry(ROOT_ROTATE_OLD_ID, old_public, "active"),
    root_rotation_entry(ROOT_ROTATE_NEW_ID, new_public, "active")
  ]
  roots3 = [
    root_rotation_entry(ROOT_ROTATE_OLD_ID, old_public, "retired"),
    root_rotation_entry(ROOT_ROTATE_NEW_ID, new_public, "active")
  ]
  policy1 = Min0CoreForth::RootPolicy.build(
    1, roots1, { ROOT_ROTATE_OLD_ID => old_private }
  )
  policy2 = Min0CoreForth::RootPolicy.build(
    2,
    roots2,
    { ROOT_ROTATE_OLD_ID => old_private, ROOT_ROTATE_NEW_ID => new_private },
    previous_policy: policy1
  )
  policy3 = Min0CoreForth::RootPolicy.build(
    3,
    roots3,
    { ROOT_ROTATE_OLD_ID => old_private, ROOT_ROTATE_NEW_ID => new_private },
    previous_policy: policy2
  )
  policy4 = Min0CoreForth::RootPolicy.build(
    4, roots3, { ROOT_ROTATE_NEW_ID => new_private }, previous_policy: policy3
  )
  Min0CoreForth::RootPolicy.validate_chain([policy1, policy2, policy3, policy4], pinned)

  root_write_power_loss = Min0CoreForth::ROOT_POLICY_INSTALL_STEPS.to_h do |step|
    store = Min0CoreForth::RootPolicyStore.new(policy1, pinned)
    begin
      store.install(policy2, fail_after: step)
    rescue Min0CoreForth::SimulatedPowerLoss
      nil
    end
    _slot, current, = store.current
    [
      step,
      {
        visible_epoch: current[:epoch],
        minimum_epoch: store.minimum_epoch.minimum_accepted
      }
    ]
  end

  root_commit_power_loss = Min0CoreForth::TRUST_COMMIT_STEPS.to_h do |step|
    store = Min0CoreForth::RootPolicyStore.new(policy1, pinned)
    store.install(policy2)
    begin
      store.commit_current(fail_after: step)
    rescue Min0CoreForth::SimulatedPowerLoss
      nil
    end
    _slot, current, = store.current
    [
      step,
      {
        visible_epoch: current[:epoch],
        minimum_epoch: store.minimum_epoch.minimum_accepted
      }
    ]
  end

  image_private = Min0CoreForth::Authentication.ed25519_private_from_seed(ED25519_TEST_SEED)
  image_public = Min0CoreForth::Authentication.ed25519_public_bytes(image_private)
  trust_keys = [root_rotation_image_entry(image_public)]
  old_root_bundle = Min0CoreForth::TrustBundle.build(
    1,
    trust_keys,
    root_key_id: ROOT_ROTATE_OLD_ID,
    root_private_key: old_private
  )
  new_root_bundle = Min0CoreForth::TrustBundle.build(
    2,
    trust_keys,
    root_key_id: ROOT_ROTATE_NEW_ID,
    root_private_key: new_private
  )

  store = Min0CoreForth::RootPolicyStore.new(policy1, pinned)
  store.install(policy2)
  store.commit_current
  _slot, overlap, = store.current
  overlap_keys = Min0CoreForth::RootPolicy.active_keys(overlap)
  Min0CoreForth::TrustBundle.validate(old_root_bundle, overlap_keys, minimum_epoch: 1)
  Min0CoreForth::TrustBundle.validate(new_root_bundle, overlap_keys, minimum_epoch: 2)

  store.install(policy3)
  store.commit_current
  _slot, retired, = store.current
  retired_keys = Min0CoreForth::RootPolicy.active_keys(retired)
  new_bundle_survives_retirement = !root_rotation_rejected(
    Min0CoreForth::RootPolicyError, Min0CoreForth::TrustError
  ) do
    Min0CoreForth::TrustBundle.validate(new_root_bundle, retired_keys, minimum_epoch: 2)
  end
  old_bundle_rejected_after_retirement = root_rotation_rejected(
    Min0CoreForth::RootPolicyError, Min0CoreForth::TrustError
  ) do
    Min0CoreForth::TrustBundle.validate(old_root_bundle, retired_keys, minimum_epoch: 1)
  end

  premature_store = Min0CoreForth::RootPolicyStore.new(policy1, pinned)
  premature_store.install(policy2)
  premature_store.commit_current
  premature_store.install(policy3)
  premature_store.commit_current
  _slot, premature_policy, = premature_store.current
  premature_retirement_breaks_old_bundle = root_rotation_rejected(
    Min0CoreForth::RootPolicyError, Min0CoreForth::TrustError
  ) do
    Min0CoreForth::TrustBundle.validate(
      old_root_bundle,
      Min0CoreForth::RootPolicy.active_keys(premature_policy),
      minimum_epoch: 1
    )
  end

  store.install(policy4)
  store.commit_current
  _slot, final_policy, = store.current

  missing_new_signature = Min0CoreForth::RootPolicy.build(
    2, roots2, { ROOT_ROTATE_OLD_ID => old_private }, previous_policy: policy1
  )
  missing_new_signature_rejected = root_rotation_rejected(Min0CoreForth::RootPolicyError) do
    Min0CoreForth::RootPolicy.validate_chain([policy1, missing_new_signature], pinned)
  end
  tampered_signature = Marshal.load(Marshal.dump(policy2))
  tampered_signature[:signatures][0][:signature_hex] = "00" * 64
  tampered_signature_rejected = root_rotation_rejected(Min0CoreForth::RootPolicyError) do
    Min0CoreForth::RootPolicy.validate_chain([policy1, tampered_signature], pinned)
  end
  broken_link = Marshal.load(Marshal.dump(policy2))
  broken_link[:previous_policy_sha256] = "00" * 32
  broken_link_rejected = root_rotation_rejected(Min0CoreForth::RootPolicyError) do
    Min0CoreForth::RootPolicy.validate_chain([policy1, broken_link], pinned)
  end
  replacement_roots = [
    root_rotation_entry(ROOT_ROTATE_OLD_ID, new_public, "active"),
    root_rotation_entry(ROOT_ROTATE_NEW_ID, new_public, "active")
  ]
  replacement = Min0CoreForth::RootPolicy.build(
    2,
    replacement_roots,
    { ROOT_ROTATE_OLD_ID => old_private, ROOT_ROTATE_NEW_ID => new_private },
    previous_policy: policy1
  )
  root_replacement_rejected = root_rotation_rejected(Min0CoreForth::RootPolicyError) do
    Min0CoreForth::RootPolicy.validate_chain([policy1, replacement], pinned)
  end
  reactivated = Min0CoreForth::RootPolicy.build(
    4,
    roots2,
    { ROOT_ROTATE_OLD_ID => old_private, ROOT_ROTATE_NEW_ID => new_private },
    previous_policy: policy3
  )
  retired_reactivation_rejected = root_rotation_rejected(Min0CoreForth::RootPolicyError) do
    Min0CoreForth::RootPolicy.validate_chain([policy1, policy2, policy3, reactivated], pinned)
  end
  root_rollback_rejected = root_rotation_rejected(Min0CoreForth::RootPolicyError) do
    store.install(policy2)
  end

  corrupt_store = Min0CoreForth::RootPolicyStore.new(policy1, pinned)
  corrupt_store.install(policy2)
  corrupt_store.commit_current
  current_slot, = corrupt_store.current
  corrupt_store.slots[current_slot].chain[-1][:epoch] = 99
  corrupted_committed_chain_fails_closed = root_rotation_rejected(Min0CoreForth::RootPolicyError) do
    corrupt_store.current
  end

  policies = [policy1, policy2, policy3, policy4]
  {
    implementation: implementation,
    root_policy_format_version: policy4[:version],
    root_public_keys: {
      old: old_public.unpack1("H*"), new: new_public.unpack1("H*")
    },
    policy_digests: policies.each_with_index.to_h do |policy, index|
      [(index + 1).to_s, Min0CoreForth::RootPolicy.digest(policy)]
    end,
    policy_signatures: policies.each_with_index.to_h do |policy, index|
      [
        (index + 1).to_s,
        policy[:signatures].to_h { |entry| [entry[:key_id], entry[:signature_hex]] }
      ]
    end,
    root_write_power_loss: root_write_power_loss,
    root_commit_power_loss: root_commit_power_loss,
    ordering: {
      overlap_accepts_old_and_new_bundles: true,
      new_bundle_survives_retirement: new_bundle_survives_retirement,
      old_bundle_rejected_after_retirement: old_bundle_rejected_after_retirement,
      premature_retirement_breaks_old_bundle: premature_retirement_breaks_old_bundle,
      post_retirement_new_root_only_policy: final_policy[:epoch] == 4
    },
    rejected: {
      missing_new_signature: missing_new_signature_rejected,
      tampered_signature: tampered_signature_rejected,
      broken_chain_link: broken_link_rejected,
      root_key_replacement: root_replacement_rejected,
      retired_root_reactivation: retired_reactivation_rejected,
      root_policy_rollback: root_rollback_rejected,
      corrupted_committed_chain_fails_closed: corrupted_committed_chain_fails_closed
    },
    final_root_epoch: store.minimum_epoch.minimum_accepted,
    final_active_roots: Min0CoreForth::RootPolicy.active_keys(final_policy).keys.sort
  }
end

if $PROGRAM_NAME == __FILE__
  puts JSON.generate(run_root_rotation_demo)
end
