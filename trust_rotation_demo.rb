# frozen_string_literal: true

require "json"
require_relative "min0_core_forth_trust"
require_relative "recovery_path_demo"

ROOT_KEY_ID = "fixture-offline-root-01"
# Public, deterministic test fixtures only. Never use these keys in deployment.
ROOT_TEST_SEED = ([0xC3] * 32).pack("C*").freeze
NORMAL_KEY2_ID = "fixture-ed25519-02"
NORMAL_KEY2_TEST_SEED = ([0xA6] * 32).pack("C*").freeze
RECOVERY_KEY2_ID = "fixture-recovery-ed25519-02"
RECOVERY_KEY2_TEST_SEED = ([0xB7] * 32).pack("C*").freeze

def trust_entry(key_id, role, public_key, status)
  {
    key_id: key_id,
    role: role,
    public_key_hex: public_key.unpack1("H*"),
    status: status
  }
end

def trust_signed_image(generation, key_id, private_key, role)
  components, template = build_source_image(generation)
  [
    components,
    signed_from_template(
      components,
      template,
      key_id,
      private_key: private_key,
      image_role: role
    )
  ]
end

def trust_rejected(*errors)
  yield
  false
rescue *errors
  true
end

def run_trust_rotation_demo(implementation = "ruby")
  root_private = Min0CoreForth::Authentication.ed25519_private_from_seed(ROOT_TEST_SEED)
  root_public = Min0CoreForth::Authentication.ed25519_public_bytes(root_private)
  pinned_roots = { ROOT_KEY_ID => root_public }
  old_normal_private = Min0CoreForth::Authentication.ed25519_private_from_seed(ED25519_TEST_SEED)
  old_normal_public = Min0CoreForth::Authentication.ed25519_public_bytes(old_normal_private)
  new_normal_private = Min0CoreForth::Authentication.ed25519_private_from_seed(NORMAL_KEY2_TEST_SEED)
  new_normal_public = Min0CoreForth::Authentication.ed25519_public_bytes(new_normal_private)
  old_recovery_private = Min0CoreForth::Authentication.ed25519_private_from_seed(RECOVERY_TEST_SEED)
  old_recovery_public = Min0CoreForth::Authentication.ed25519_public_bytes(old_recovery_private)
  new_recovery_private = Min0CoreForth::Authentication.ed25519_private_from_seed(RECOVERY_KEY2_TEST_SEED)
  new_recovery_public = Min0CoreForth::Authentication.ed25519_public_bytes(new_recovery_private)

  epoch1_keys = [
    trust_entry(SIGNED_IMAGE_KEY_ID, Min0CoreForth::IMAGE_ROLE_NORMAL, old_normal_public, "active"),
    trust_entry(RECOVERY_KEY_ID, Min0CoreForth::IMAGE_ROLE_RECOVERY, old_recovery_public, "active")
  ]
  epoch2_keys = [
    trust_entry(SIGNED_IMAGE_KEY_ID, Min0CoreForth::IMAGE_ROLE_NORMAL, old_normal_public, "active"),
    trust_entry(NORMAL_KEY2_ID, Min0CoreForth::IMAGE_ROLE_NORMAL, new_normal_public, "active"),
    trust_entry(RECOVERY_KEY_ID, Min0CoreForth::IMAGE_ROLE_RECOVERY, old_recovery_public, "active"),
    trust_entry(RECOVERY_KEY2_ID, Min0CoreForth::IMAGE_ROLE_RECOVERY, new_recovery_public, "active")
  ]
  epoch3_keys = [
    trust_entry(SIGNED_IMAGE_KEY_ID, Min0CoreForth::IMAGE_ROLE_NORMAL, old_normal_public, "revoked"),
    trust_entry(NORMAL_KEY2_ID, Min0CoreForth::IMAGE_ROLE_NORMAL, new_normal_public, "active"),
    trust_entry(RECOVERY_KEY_ID, Min0CoreForth::IMAGE_ROLE_RECOVERY, old_recovery_public, "active"),
    trust_entry(RECOVERY_KEY2_ID, Min0CoreForth::IMAGE_ROLE_RECOVERY, new_recovery_public, "active")
  ]
  epoch4_keys = [
    trust_entry(SIGNED_IMAGE_KEY_ID, Min0CoreForth::IMAGE_ROLE_NORMAL, old_normal_public, "revoked"),
    trust_entry(NORMAL_KEY2_ID, Min0CoreForth::IMAGE_ROLE_NORMAL, new_normal_public, "active"),
    trust_entry(RECOVERY_KEY_ID, Min0CoreForth::IMAGE_ROLE_RECOVERY, old_recovery_public, "revoked"),
    trust_entry(RECOVERY_KEY2_ID, Min0CoreForth::IMAGE_ROLE_RECOVERY, new_recovery_public, "active")
  ]
  bundles = {
    1 => Min0CoreForth::TrustBundle.build(
      1, epoch1_keys, root_key_id: ROOT_KEY_ID, root_private_key: root_private
    ),
    2 => Min0CoreForth::TrustBundle.build(
      2, epoch2_keys, root_key_id: ROOT_KEY_ID, root_private_key: root_private
    ),
    3 => Min0CoreForth::TrustBundle.build(
      3, epoch3_keys, root_key_id: ROOT_KEY_ID, root_private_key: root_private
    ),
    4 => Min0CoreForth::TrustBundle.build(
      4, epoch4_keys, root_key_id: ROOT_KEY_ID, root_private_key: root_private
    )
  }

  bundle_power_loss = {}
  Min0CoreForth::TRUST_BUNDLE_INSTALL_STEPS.each do |step|
    store = Min0CoreForth::TrustBundleStore.new(bundles[1], pinned_roots)
    begin
      store.install(bundles[2], fail_after: step)
    rescue Min0CoreForth::SimulatedPowerLoss
      # Inspect durable state below.
    end
    _index, current, = store.current
    bundle_power_loss[step] = {
      visible_epoch: current[:epoch],
      minimum_epoch: store.minimum_epoch.minimum_accepted
    }
  end

  epoch_commit_power_loss = {}
  Min0CoreForth::TRUST_COMMIT_STEPS.each do |step|
    store = Min0CoreForth::TrustBundleStore.new(bundles[1], pinned_roots)
    store.install(bundles[2])
    begin
      store.commit_current(fail_after: step)
    rescue Min0CoreForth::SimulatedPowerLoss
      # Inspect durable state below.
    end
    _index, current, = store.current
    epoch_commit_power_loss[step] = {
      visible_epoch: current[:epoch],
      minimum_epoch: store.minimum_epoch.minimum_accepted
    }
  end

  old_normal_components, old_normal_envelope = trust_signed_image(
    8, SIGNED_IMAGE_KEY_ID, old_normal_private, Min0CoreForth::IMAGE_ROLE_NORMAL
  )
  new_normal_components, new_normal_envelope = trust_signed_image(
    9, NORMAL_KEY2_ID, new_normal_private, Min0CoreForth::IMAGE_ROLE_NORMAL
  )
  Min0CoreForth::TrustBundle.validate_image(
    old_normal_components,
    old_normal_envelope,
    bundles[2],
    pinned_roots,
    role: Min0CoreForth::IMAGE_ROLE_NORMAL,
    minimum_generation: 8,
    minimum_trust_epoch: 2
  )
  Min0CoreForth::TrustBundle.validate_image(
    new_normal_components,
    new_normal_envelope,
    bundles[2],
    pinned_roots,
    role: Min0CoreForth::IMAGE_ROLE_NORMAL,
    minimum_generation: 8,
    minimum_trust_epoch: 2
  )
  old_normal_revoked = trust_rejected(Min0CoreForth::TrustError, Min0CoreForth::ImageError) do
    Min0CoreForth::TrustBundle.validate_image(
      old_normal_components,
      old_normal_envelope,
      bundles[3],
      pinned_roots,
      role: Min0CoreForth::IMAGE_ROLE_NORMAL,
      minimum_generation: 8,
      minimum_trust_epoch: 3
    )
  end
  Min0CoreForth::TrustBundle.validate_image(
    new_normal_components,
    new_normal_envelope,
    bundles[3],
    pinned_roots,
    role: Min0CoreForth::IMAGE_ROLE_NORMAL,
    minimum_generation: 8,
    minimum_trust_epoch: 3
  )

  old_recovery_components, old_recovery_envelope = trust_signed_image(
    1, RECOVERY_KEY_ID, old_recovery_private, Min0CoreForth::IMAGE_ROLE_RECOVERY
  )
  new_recovery_components, new_recovery_envelope = trust_signed_image(
    2, RECOVERY_KEY2_ID, new_recovery_private, Min0CoreForth::IMAGE_ROLE_RECOVERY
  )
  validated_epoch2 = Min0CoreForth::TrustBundle.validate(
    bundles[2], pinned_roots, minimum_epoch: 2
  )
  recovery_overlap_keys = Min0CoreForth::TrustBundle.active_keys(
    validated_epoch2, Min0CoreForth::IMAGE_ROLE_RECOVERY
  )

  recovery_update_power_loss = {}
  Min0CoreForth::INSTALL_STEPS.each do |step|
    recovery_store = Min0CoreForth::PersistentABStore.new(
      old_recovery_components, old_recovery_envelope, 1
    )
    updater = Min0CoreForth::TransactionalInstaller.new(
      recovery_store,
      recovery_overlap_keys,
      required_image_role: Min0CoreForth::IMAGE_ROLE_RECOVERY
    )
    begin
      updater.install(
        new_recovery_components, new_recovery_envelope, fail_after: step
      )
    rescue Min0CoreForth::SimulatedPowerLoss
      # Inspect durable state below.
    end
    boot = updater.select_boot
    recovery_update_power_loss[step] = {
      generation: boot[:generation],
      slot: boot[:slot],
      minimum_generation: recovery_store.trusted.minimum_accepted
    }
  end

  recovery_store = Min0CoreForth::PersistentABStore.new(
    old_recovery_components, old_recovery_envelope, 1
  )
  updater = Min0CoreForth::TransactionalInstaller.new(
    recovery_store,
    recovery_overlap_keys,
    required_image_role: Min0CoreForth::IMAGE_ROLE_RECOVERY
  )
  new_recovery_slot = updater.install(new_recovery_components, new_recovery_envelope)
  updater.report_boot_success(new_recovery_slot)
  validated_epoch4 = Min0CoreForth::TrustBundle.validate(
    bundles[4], pinned_roots, minimum_epoch: 4
  )
  post_revoke_updater = Min0CoreForth::TransactionalInstaller.new(
    recovery_store,
    Min0CoreForth::TrustBundle.active_keys(validated_epoch4, Min0CoreForth::IMAGE_ROLE_RECOVERY),
    required_image_role: Min0CoreForth::IMAGE_ROLE_RECOVERY
  )
  post_revoke_recovery_boot = post_revoke_updater.select_boot

  premature_store = Min0CoreForth::PersistentABStore.new(
    old_recovery_components, old_recovery_envelope, 1
  )
  premature_updater = Min0CoreForth::TransactionalInstaller.new(
    premature_store,
    Min0CoreForth::TrustBundle.active_keys(validated_epoch4, Min0CoreForth::IMAGE_ROLE_RECOVERY),
    required_image_role: Min0CoreForth::IMAGE_ROLE_RECOVERY
  )
  premature_revoke_breaks_old_recovery = trust_rejected(Min0CoreForth::BootError) do
    premature_updater.select_boot
  end

  trust_store = Min0CoreForth::TrustBundleStore.new(bundles[1], pinned_roots)
  [2, 3, 4].each do |epoch|
    trust_store.install(bundles[epoch])
    trust_store.commit_current
  end
  bundle_rollback_rejected = trust_rejected(Min0CoreForth::TrustError) do
    trust_store.install(bundles[1])
  end

  attacker_private = Min0CoreForth::Authentication.ed25519_private_from_seed(
    ([0xEE] * 32).pack("C*")
  )
  forged = Min0CoreForth::TrustBundle.build(
    5,
    epoch4_keys,
    root_key_id: ROOT_KEY_ID,
    root_private_key: attacker_private
  )
  forged_bundle_rejected = trust_rejected(Min0CoreForth::TrustError) do
    Min0CoreForth::TrustBundle.validate(forged, pinned_roots, minimum_epoch: 4)
  end
  tampered = Marshal.load(Marshal.dump(bundles[4]))
  tampered[:keys][0][:status] = "active"
  tampered_bundle_rejected = trust_rejected(Min0CoreForth::TrustError) do
    Min0CoreForth::TrustBundle.validate(tampered, pinned_roots, minimum_epoch: 4)
  end

  {
    implementation: implementation,
    bundle_format_version: bundles[4][:version],
    root_public_key_hex: root_public.unpack1("H*"),
    bundle_signatures: [1, 2, 3, 4].to_h do |epoch|
      [epoch.to_s, bundles[epoch][:signature][:signature_hex]]
    end,
    bundle_power_loss: bundle_power_loss,
    epoch_commit_power_loss: epoch_commit_power_loss,
    normal_rotation: {
      overlap_accepts_old_and_new: true,
      old_revoked_at_epoch3: old_normal_revoked,
      new_survives_epoch3: true
    },
    recovery_update_power_loss: recovery_update_power_loss,
    post_revoke_recovery_boot: post_revoke_recovery_boot,
    ordering: {
      premature_revoke_breaks_old_recovery: premature_revoke_breaks_old_recovery,
      correct_order_keeps_new_recovery: post_revoke_recovery_boot[:generation] == 2
    },
    rejected: {
      bundle_rollback: bundle_rollback_rejected,
      forged_root_signature: forged_bundle_rejected,
      tampered_bundle: tampered_bundle_rejected
    },
    final_trust_epoch: trust_store.minimum_epoch.minimum_accepted
  }
end

puts JSON.generate(run_trust_rotation_demo) if $PROGRAM_NAME == __FILE__
