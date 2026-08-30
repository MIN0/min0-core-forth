# frozen_string_literal: true

require "json"
require_relative "min0_core_forth_recovery"
require_relative "signed_image_demo"

RECOVERY_KEY_ID = "fixture-recovery-ed25519-01"
# Public, deterministic test fixture only. Never use this key in deployment.
RECOVERY_TEST_SEED = ([0x5A] * 32).pack("C*").freeze

def recovery_normal_image(generation)
  components, template = build_source_image(generation)
  [components, signed_from_template(components, template, SIGNED_IMAGE_KEY_ID)]
end

def recovery_role_image
  components, template = build_source_image(1)
  private_key = Min0CoreForth::Authentication.ed25519_private_from_seed(RECOVERY_TEST_SEED)
  envelope = signed_from_template(
    components,
    template,
    RECOVERY_KEY_ID,
    private_key: private_key,
    image_role: Min0CoreForth::IMAGE_ROLE_RECOVERY
  )
  [components, envelope, Min0CoreForth::Authentication.ed25519_public_bytes(private_key)]
end

def failed_normal_state(normal_public_key)
  old_components, old_envelope = recovery_normal_image(7)
  new_components, new_envelope = recovery_normal_image(8)
  store = Min0CoreForth::PersistentABStore.new(old_components, old_envelope, 7)
  installer = Min0CoreForth::TransactionalInstaller.new(
    store, { SIGNED_IMAGE_KEY_ID => normal_public_key }
  )
  new_slot = installer.install(new_components, new_envelope)
  installer.report_boot_success(new_slot)
  changed = store.slots[new_slot].components["code"].dup
  last = changed.bytesize - 1
  changed.setbyte(last, changed.getbyte(last) ^ 1)
  store.slots[new_slot].components["code"] = changed
  [store, installer]
end

def recovery_manager(normal_public_key, recovery_components, recovery_envelope, recovery_public_key)
  store, installer = failed_normal_state(normal_public_key)
  recovery_store = Min0CoreForth::ProtectedRecoveryStore.new(
    recovery_components, recovery_envelope, 1
  )
  manager = Min0CoreForth::RecoveryBootManager.new(
    installer, recovery_store, { RECOVERY_KEY_ID => recovery_public_key }
  )
  [store, installer, recovery_store, manager]
end

def recovery_rejected(*errors)
  yield
  false
rescue *errors
  true
end

def run_recovery_path_demo(implementation = "ruby")
  normal_public_key = Min0CoreForth::Authentication.ed25519_public_bytes(
    Min0CoreForth::Authentication.ed25519_private_from_seed(ED25519_TEST_SEED)
  )
  recovery_components, recovery_envelope, recovery_public_key = recovery_role_image
  repair_components, repair_envelope = recovery_normal_image(8)
  old_components, old_envelope = recovery_normal_image(7)

  store, installer, recovery_store, manager = recovery_manager(
    normal_public_key, recovery_components, recovery_envelope, recovery_public_key
  )
  recovery_boot = manager.select_boot

  repair_power_loss = {}
  Min0CoreForth::INSTALL_STEPS.each do |step|
    cut_store, _cut_installer, _cut_recovery_store, cut_manager = recovery_manager(
      normal_public_key, recovery_components, recovery_envelope, recovery_public_key
    )
    begin
      cut_manager.repair_normal(
        repair_components, repair_envelope, target_slot: "B", fail_after: step
      )
    rescue Min0CoreForth::SimulatedPowerLoss
      # Select from durable state below.
    end
    boot = cut_manager.select_boot
    repair_power_loss[step] = {
      mode: boot[:mode],
      generation: boot[:generation],
      normal_trusted_generation: cut_store.trusted.minimum_accepted
    }
  end

  repaired_slot = manager.repair_normal(
    repair_components, repair_envelope, target_slot: "B"
  )
  repaired_boot = manager.select_boot
  installer.report_boot_success(repaired_slot)

  store2, _installer2, _recovery_store2, manager2 = recovery_manager(
    normal_public_key, recovery_components, recovery_envelope, recovery_public_key
  )
  old_repair_rejected = recovery_rejected(Min0CoreForth::ImageError, Min0CoreForth::InstallError) do
    manager2.repair_normal(old_components, old_envelope, target_slot: "B")
  end

  normal_components, normal_envelope = recovery_normal_image(8)
  wrong_recovery_store = Min0CoreForth::ProtectedRecoveryStore.new(
    normal_components, normal_envelope, 1
  )
  wrong_role_manager = Min0CoreForth::RecoveryBootManager.new(
    manager2.normal_installer,
    wrong_recovery_store,
    { SIGNED_IMAGE_KEY_ID => normal_public_key }
  )
  normal_as_recovery_rejected = recovery_rejected(Min0CoreForth::BootError) do
    wrong_role_manager.select_boot
  end

  combined_installer = Min0CoreForth::TransactionalInstaller.new(
    store2,
    {
      SIGNED_IMAGE_KEY_ID => normal_public_key,
      RECOVERY_KEY_ID => recovery_public_key
    }
  )
  recovery_as_normal_rejected = recovery_rejected(
    Min0CoreForth::ImageError, Min0CoreForth::InstallError
  ) do
    combined_installer.repair_install(
      recovery_components, recovery_envelope, target_slot: "B"
    )
  end

  tampered_recovery = Marshal.load(Marshal.dump(recovery_envelope))
  tampered_recovery[:image_role] = "normal"
  tampered_store = Min0CoreForth::ProtectedRecoveryStore.new(
    recovery_components, tampered_recovery, 1
  )
  tampered_manager = Min0CoreForth::RecoveryBootManager.new(
    manager2.normal_installer,
    tampered_store,
    { RECOVERY_KEY_ID => recovery_public_key }
  )
  role_tamper_rejected = recovery_rejected(Min0CoreForth::BootError) do
    tampered_manager.select_boot
  end

  corrupt_recovery_components = recovery_components.transform_values(&:dup)
  corrupt_code = corrupt_recovery_components[:code]
  last = corrupt_code.bytesize - 1
  corrupt_code.setbyte(last, corrupt_code.getbyte(last) ^ 1)
  corrupt_recovery_store = Min0CoreForth::ProtectedRecoveryStore.new(
    corrupt_recovery_components, recovery_envelope, 1
  )
  corrupt_recovery_manager = Min0CoreForth::RecoveryBootManager.new(
    manager2.normal_installer,
    corrupt_recovery_store,
    { RECOVERY_KEY_ID => recovery_public_key }
  )
  total_failure_visible = recovery_rejected(Min0CoreForth::BootError) do
    corrupt_recovery_manager.select_boot
  end

  healthy_old_components, healthy_old_envelope = recovery_normal_image(7)
  healthy_store = Min0CoreForth::PersistentABStore.new(
    healthy_old_components, healthy_old_envelope, 7
  )
  healthy_installer = Min0CoreForth::TransactionalInstaller.new(
    healthy_store, { SIGNED_IMAGE_KEY_ID => normal_public_key }
  )
  healthy_recovery_store = Min0CoreForth::ProtectedRecoveryStore.new(
    recovery_components, recovery_envelope, 1
  )
  healthy_manager = Min0CoreForth::RecoveryBootManager.new(
    healthy_installer,
    healthy_recovery_store,
    { RECOVERY_KEY_ID => recovery_public_key }
  )
  repair_outside_recovery_rejected = recovery_rejected(
    Min0CoreForth::ImageError, Min0CoreForth::InstallError
  ) do
    healthy_manager.repair_normal(
      repair_components, repair_envelope, target_slot: "B"
    )
  end

  {
    implementation: implementation,
    format_version: recovery_envelope[:version],
    recovery_identity: recovery_envelope[:identity_sha256],
    recovery_role: recovery_envelope[:image_role],
    recovery_boot: recovery_boot,
    repair_steps: Min0CoreForth::INSTALL_STEPS,
    repair_power_loss: repair_power_loss,
    repaired_boot: repaired_boot,
    normal_trusted_after_repair: store.trusted.minimum_accepted,
    separate_generations: {
      normal: store.trusted.minimum_accepted,
      recovery: recovery_store.trusted.minimum_accepted
    },
    rejected: {
      old_normal_repair: old_repair_rejected,
      normal_as_recovery: normal_as_recovery_rejected,
      recovery_as_normal: recovery_as_normal_rejected,
      role_tamper: role_tamper_rejected,
      repair_outside_recovery: repair_outside_recovery_rejected
    },
    corrupt_recovery_total_failure_visible: total_failure_visible
  }
end

puts JSON.generate(run_recovery_path_demo) if $PROGRAM_NAME == __FILE__
