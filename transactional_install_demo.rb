# frozen_string_literal: true

require "json"
require_relative "min0_core_forth_install"
require_relative "signed_image_demo"

def transactional_signed_image(generation)
  components, template = build_source_image(generation)
  [components, signed_from_template(components, template, SIGNED_IMAGE_KEY_ID)]
end

def fresh_transactional_store(old_components, old_envelope, trusted)
  store = Min0CoreForth::PersistentABStore.new(old_components, old_envelope, 7)
  [store, Min0CoreForth::TransactionalInstaller.new(store, trusted)]
end

def run_transactional_install_demo(implementation = "ruby")
  old_components, old_envelope = transactional_signed_image(7)
  new_components, new_envelope = transactional_signed_image(8)
  rollback_components, rollback_envelope = transactional_signed_image(6)
  public_key = Min0CoreForth::Authentication.ed25519_public_bytes(
    Min0CoreForth::Authentication.ed25519_private_from_seed(ED25519_TEST_SEED)
  )
  trusted = { SIGNED_IMAGE_KEY_ID => public_key }

  install_power_loss = {}
  Min0CoreForth::INSTALL_STEPS.each do |step|
    store, installer = fresh_transactional_store(old_components, old_envelope, trusted)
    begin
      installer.install(new_components, new_envelope, fail_after: step)
    rescue Min0CoreForth::SimulatedPowerLoss
      # Reboot from durable state below.
    end
    boot = installer.select_boot
    install_power_loss[step] = {
      boot_generation: boot[:generation],
      boot_slot: boot[:slot],
      trusted_generation: store.trusted.minimum_accepted
    }
  end

  trust_power_loss = {}
  Min0CoreForth::TRUST_COMMIT_STEPS.each do |step|
    store, installer = fresh_transactional_store(old_components, old_envelope, trusted)
    new_slot = installer.install(new_components, new_envelope)
    begin
      installer.report_boot_success(new_slot, fail_after: step)
    rescue Min0CoreForth::SimulatedPowerLoss
      # Reboot from durable journal below.
    end
    boot = installer.select_boot
    trust_power_loss[step] = {
      boot_generation: boot[:generation],
      boot_slot: boot[:slot],
      trusted_generation: store.trusted.minimum_accepted
    }
  end

  store, installer = fresh_transactional_store(old_components, old_envelope, trusted)
  new_slot = installer.install(new_components, new_envelope)
  pending_boot = installer.select_boot
  installer.report_boot_failure(new_slot)
  fallback_boot = installer.select_boot

  store2, installer2 = fresh_transactional_store(old_components, old_envelope, trusted)
  corrupted_slot = installer2.install(new_components, new_envelope)
  changed = store2.slots[corrupted_slot].components["code"].dup
  last = changed.bytesize - 1
  changed.setbyte(last, changed.getbyte(last) ^ 1)
  store2.slots[corrupted_slot].components["code"] = changed
  corrupted_fallback = installer2.select_boot

  store3, installer3 = fresh_transactional_store(old_components, old_envelope, trusted)
  marker_slot = installer3.install(new_components, new_envelope)
  marker = store3.slots[marker_slot].marker
  original_marker_checksum = marker.checksum
  marker.checksum = (original_marker_checksum[0] == "0" ? "1" : "0") + original_marker_checksum[1..]
  marker_fallback = installer3.select_boot

  store4, installer4 = fresh_transactional_store(old_components, old_envelope, trusted)
  rollback_rejected = begin
    installer4.install(rollback_components, rollback_envelope)
    false
  rescue Min0CoreForth::ImageError
    true
  end
  unchanged_after_rollback = installer4.select_boot

  store5, installer5 = fresh_transactional_store(old_components, old_envelope, trusted)
  committed_slot = installer5.install(new_components, new_envelope)
  committed_generation = installer5.report_boot_success(committed_slot)
  newest_record_index = store5.trusted.current[0]
  newest_record = store5.trusted.records[newest_record_index]
  original_trusted_checksum = newest_record.checksum
  newest_record.checksum =
    (original_trusted_checksum[0] == "0" ? "1" : "0") + original_trusted_checksum[1..]
  journal_fallback_generation = store5.trusted.minimum_accepted
  journal_fallback_boot = installer5.select_boot

  store6, installer6 = fresh_transactional_store(old_components, old_envelope, trusted)
  committed_slot2 = installer6.install(new_components, new_envelope)
  installer6.report_boot_success(committed_slot2)
  changed2 = store6.slots[committed_slot2].components["code"].dup
  last2 = changed2.bytesize - 1
  changed2.setbyte(last2, changed2.getbyte(last2) ^ 1)
  store6.slots[committed_slot2].components["code"] = changed2
  recovery_required = begin
    installer6.select_boot
    false
  rescue Min0CoreForth::BootError
    true
  end

  {
    implementation: implementation,
    install_steps: Min0CoreForth::INSTALL_STEPS,
    trust_commit_steps: Min0CoreForth::TRUST_COMMIT_STEPS,
    install_power_loss: install_power_loss,
    trust_power_loss: trust_power_loss,
    pending_boot: pending_boot,
    failed_boot_fallback: fallback_boot,
    corrupted_candidate_fallback: corrupted_fallback,
    torn_marker_fallback: marker_fallback,
    rollback_rejected: rollback_rejected,
    unchanged_after_rollback: unchanged_after_rollback,
    successful_commit_generation: committed_generation,
    trusted_journal_corruption: {
      fallback_generation: journal_fallback_generation,
      boot_generation: journal_fallback_boot[:generation]
    },
    post_commit_active_corruption_requires_recovery: recovery_required
  }
end

puts JSON.generate(run_transactional_install_demo) if $PROGRAM_NAME == __FILE__
