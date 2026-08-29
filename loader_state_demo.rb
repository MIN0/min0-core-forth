# frozen_string_literal: true

require "json"
require_relative "min0_core_forth_loader"
require_relative "trust_rotation_demo"
require_relative "root_rotation_demo"

def loader_root_entry(key_id, public_key, status)
  {
    key_id: key_id,
    public_key_hex: public_key.unpack1("H*"),
    status: status
  }
end

def loader_trust_entry(key_id, role, public_key, status)
  {
    key_id: key_id,
    role: role,
    public_key_hex: public_key.unpack1("H*"),
    status: status
  }
end

def loader_rejected
  yield
  false
rescue Min0CoreForth::LoaderError, Min0CoreForth::RootPolicyError, Min0CoreForth::TrustError,
       Min0CoreForth::ImageError, Min0CoreForth::PersistentFormatError,
       Min0CoreForth::GenerationError, Min0CoreForth::InstallError, ArgumentError
  true
end

def loader_fixtures
  old_root_private = Min0CoreForth::Authentication.ed25519_private_from_seed(ROOT_ROTATE_OLD_TEST_SEED)
  new_root_private = Min0CoreForth::Authentication.ed25519_private_from_seed(ROOT_ROTATE_NEW_TEST_SEED)
  old_root_public = Min0CoreForth::Authentication.ed25519_public_bytes(old_root_private)
  new_root_public = Min0CoreForth::Authentication.ed25519_public_bytes(new_root_private)
  old_normal_private = Min0CoreForth::Authentication.ed25519_private_from_seed(ED25519_TEST_SEED)
  new_normal_private = Min0CoreForth::Authentication.ed25519_private_from_seed(NORMAL_KEY2_TEST_SEED)
  old_recovery_private = Min0CoreForth::Authentication.ed25519_private_from_seed(RECOVERY_TEST_SEED)
  new_recovery_private = Min0CoreForth::Authentication.ed25519_private_from_seed(RECOVERY_KEY2_TEST_SEED)
  old_normal_public = Min0CoreForth::Authentication.ed25519_public_bytes(old_normal_private)
  new_normal_public = Min0CoreForth::Authentication.ed25519_public_bytes(new_normal_private)
  old_recovery_public = Min0CoreForth::Authentication.ed25519_public_bytes(old_recovery_private)
  new_recovery_public = Min0CoreForth::Authentication.ed25519_public_bytes(new_recovery_private)

  roots1 = [loader_root_entry(ROOT_ROTATE_OLD_ID, old_root_public, "active")]
  roots2 = [
    loader_root_entry(ROOT_ROTATE_OLD_ID, old_root_public, "active"),
    loader_root_entry(ROOT_ROTATE_NEW_ID, new_root_public, "active")
  ]
  roots3 = [
    loader_root_entry(ROOT_ROTATE_OLD_ID, old_root_public, "retired"),
    loader_root_entry(ROOT_ROTATE_NEW_ID, new_root_public, "active")
  ]
  policy1 = Min0CoreForth::RootPolicy.build(
    1, roots1, { ROOT_ROTATE_OLD_ID => old_root_private }
  )
  policy2 = Min0CoreForth::RootPolicy.build(
    2,
    roots2,
    { ROOT_ROTATE_OLD_ID => old_root_private, ROOT_ROTATE_NEW_ID => new_root_private },
    previous_policy: policy1
  )
  policy3 = Min0CoreForth::RootPolicy.build(
    3,
    roots3,
    { ROOT_ROTATE_OLD_ID => old_root_private, ROOT_ROTATE_NEW_ID => new_root_private },
    previous_policy: policy2
  )

  keys1 = [
    loader_trust_entry(
      SIGNED_IMAGE_KEY_ID, Min0CoreForth::IMAGE_ROLE_NORMAL, old_normal_public, "active"
    ),
    loader_trust_entry(
      RECOVERY_KEY_ID, Min0CoreForth::IMAGE_ROLE_RECOVERY, old_recovery_public, "active"
    )
  ]
  keys2 = keys1 + [
    loader_trust_entry(
      NORMAL_KEY2_ID, Min0CoreForth::IMAGE_ROLE_NORMAL, new_normal_public, "active"
    ),
    loader_trust_entry(
      RECOVERY_KEY2_ID, Min0CoreForth::IMAGE_ROLE_RECOVERY, new_recovery_public, "active"
    )
  ]
  keys3 = [
    loader_trust_entry(
      SIGNED_IMAGE_KEY_ID, Min0CoreForth::IMAGE_ROLE_NORMAL, old_normal_public, "revoked"
    ),
    loader_trust_entry(
      NORMAL_KEY2_ID, Min0CoreForth::IMAGE_ROLE_NORMAL, new_normal_public, "active"
    ),
    loader_trust_entry(
      RECOVERY_KEY_ID, Min0CoreForth::IMAGE_ROLE_RECOVERY, old_recovery_public, "revoked"
    ),
    loader_trust_entry(
      RECOVERY_KEY2_ID, Min0CoreForth::IMAGE_ROLE_RECOVERY, new_recovery_public, "active"
    )
  ]
  bundle1 = Min0CoreForth::TrustBundle.build(
    1, keys1, root_key_id: ROOT_ROTATE_OLD_ID, root_private_key: old_root_private
  )
  bundle2 = Min0CoreForth::TrustBundle.build(
    2, keys2, root_key_id: ROOT_ROTATE_NEW_ID, root_private_key: new_root_private
  )
  bundle3 = Min0CoreForth::TrustBundle.build(
    3, keys3, root_key_id: ROOT_ROTATE_NEW_ID, root_private_key: new_root_private
  )
  normal1 = trust_signed_image(
    1, SIGNED_IMAGE_KEY_ID, old_normal_private, Min0CoreForth::IMAGE_ROLE_NORMAL
  )
  normal2 = trust_signed_image(
    2, NORMAL_KEY2_ID, new_normal_private, Min0CoreForth::IMAGE_ROLE_NORMAL
  )
  recovery1 = trust_signed_image(
    1, RECOVERY_KEY_ID, old_recovery_private, Min0CoreForth::IMAGE_ROLE_RECOVERY
  )
  recovery2 = trust_signed_image(
    2, RECOVERY_KEY2_ID, new_recovery_private, Min0CoreForth::IMAGE_ROLE_RECOVERY
  )
  {
    pinned: { ROOT_ROTATE_OLD_ID => old_root_public },
    policies: [policy1, policy2, policy3],
    bundles: [bundle1, bundle2, bundle3],
    normal: [normal1, normal2],
    recovery: [recovery1, recovery2],
    packages: {
      root2: Min0CoreForth::PersistentPackage.encode_root_policy_chain([policy1, policy2]),
      root3: Min0CoreForth::PersistentPackage.encode_root_policy_chain([policy1, policy2, policy3]),
      trust2: Min0CoreForth::PersistentPackage.encode_trust_bundle(bundle2),
      trust3: Min0CoreForth::PersistentPackage.encode_trust_bundle(bundle3),
      normal1: Min0CoreForth::PersistentPackage.encode_image(*normal1),
      normal2: Min0CoreForth::PersistentPackage.encode_image(*normal2),
      recovery2: Min0CoreForth::PersistentPackage.encode_image(*recovery2)
    }
  }
end

def make_loader(fixture)
  Min0CoreForth::Loader.new(
    fixture[:policies][0],
    fixture[:pinned],
    fixture[:bundles][0],
    *fixture[:normal][0],
    *fixture[:recovery][0]
  )
end

def advance_loader_to_overlap(loader, packages)
  loader.stage_root_package(packages[:root2])
  loader.commit_root
  loader.stage_trust_package(packages[:trust2])
  loader.commit_trust
end

def run_loader_state_demo(implementation = "ruby")
  fixture = loader_fixtures
  packages = fixture[:packages]

  loader = make_loader(fixture)
  initial = loader.status
  advance_loader_to_overlap(loader, packages)
  normal_slot = loader.stage_image_package(
    packages[:normal2], role: Min0CoreForth::IMAGE_ROLE_NORMAL
  )
  loader.commit_image(Min0CoreForth::IMAGE_ROLE_NORMAL, normal_slot)
  recovery_slot = loader.stage_image_package(
    packages[:recovery2], role: Min0CoreForth::IMAGE_ROLE_RECOVERY
  )
  loader.commit_image(Min0CoreForth::IMAGE_ROLE_RECOVERY, recovery_slot)
  loader.stage_trust_package(packages[:trust3])
  loader.commit_trust
  loader.stage_root_package(packages[:root3])
  loader.commit_root
  final = loader.status

  premature_root = make_loader(fixture)
  premature_root.stage_root_package(packages[:root2])
  premature_root.commit_root
  premature_root_retirement_rejected = loader_rejected do
    premature_root.stage_root_package(packages[:root3])
  end

  premature_trust = make_loader(fixture)
  advance_loader_to_overlap(premature_trust, packages)
  premature_key_revocation_rejected = loader_rejected do
    premature_trust.stage_trust_package(packages[:trust3])
  end

  trust_before_root = make_loader(fixture)
  new_root_bundle_before_overlap_rejected = loader_rejected do
    trust_before_root.stage_trust_package(packages[:trust2])
  end

  wrong_role = make_loader(fixture)
  advance_loader_to_overlap(wrong_role, packages)
  role_confusion_rejected = loader_rejected do
    wrong_role.stage_image_package(
      packages[:recovery2], role: Min0CoreForth::IMAGE_ROLE_NORMAL
    )
  end
  image_rollback_rejected = loader_rejected do
    wrong_role.stage_image_package(
      packages[:normal1], role: Min0CoreForth::IMAGE_ROLE_NORMAL
    )
  end
  malformed_package_rejected = loader_rejected do
    wrong_role.stage_image_package(
      packages[:normal2].byteslice(0, packages[:normal2].bytesize - 1),
      role: Min0CoreForth::IMAGE_ROLE_NORMAL
    )
  end

  tampered_history = Marshal.load(Marshal.dump(fixture[:policies][0]))
  tampered_history[:epoch] = 0
  history_package = Min0CoreForth::PersistentPackage.encode_root_policy_chain(
    [tampered_history, fixture[:policies][1]]
  )
  root_history_mismatch_rejected = loader_rejected do
    make_loader(fixture).stage_root_package(history_package)
  end

  failed_boot = make_loader(fixture)
  advance_loader_to_overlap(failed_boot, packages)
  failed_slot = failed_boot.stage_image_package(
    packages[:normal2], role: Min0CoreForth::IMAGE_ROLE_NORMAL
  )
  failed_boot.reject_image(Min0CoreForth::IMAGE_ROLE_NORMAL, failed_slot)
  failed_status = failed_boot.status
  boot_failure_returns_old_generation =
    failed_status[:normal_generation] == 1 && failed_boot.phase == "stable"

  recovery_fallback = make_loader(fixture)
  recovery_fallback.normal_store.slots.fetch("A").marker = nil
  recovery_status = recovery_fallback.status
  all_normal_failure_selects_recovery =
    recovery_status[:phase] == "stable" &&
    recovery_status[:normal_generation].nil? &&
    recovery_status[:boot][:mode] == "recovery" &&
    recovery_status[:boot][:generation] == 1

  root_stage_power_loss = Min0CoreForth::ROOT_POLICY_INSTALL_STEPS.to_h do |step|
    cut_loader = make_loader(fixture)
    begin
      cut_loader.stage_root_package(packages[:root2], fail_after: step)
    rescue Min0CoreForth::SimulatedPowerLoss
      nil
    end
    state = cut_loader.status
    [
      step,
      {
        root_epoch: state[:root_epoch],
        minimum_epoch: state[:minimum_root_epoch],
        phase: state[:phase]
      }
    ]
  end

  root_commit_power_loss = Min0CoreForth::TRUST_COMMIT_STEPS.to_h do |step|
    cut_loader = make_loader(fixture)
    cut_loader.stage_root_package(packages[:root2])
    begin
      cut_loader.commit_root(fail_after: step)
    rescue Min0CoreForth::SimulatedPowerLoss
      nil
    end
    state = cut_loader.status
    [
      step,
      {
        root_epoch: state[:root_epoch],
        minimum_epoch: state[:minimum_root_epoch],
        phase: state[:phase]
      }
    ]
  end

  {
    implementation: implementation,
    initial: initial,
    final: final,
    history: loader.history,
    ordering: {
      premature_root_retirement_rejected: premature_root_retirement_rejected,
      premature_key_revocation_rejected: premature_key_revocation_rejected,
      new_root_bundle_before_overlap_rejected: new_root_bundle_before_overlap_rejected,
      boot_failure_returns_old_generation: boot_failure_returns_old_generation,
      all_normal_failure_selects_recovery: all_normal_failure_selects_recovery
    },
    rejected: {
      role_confusion: role_confusion_rejected,
      image_rollback: image_rollback_rejected,
      malformed_package: malformed_package_rejected,
      root_history_mismatch: root_history_mismatch_rejected
    },
    root_stage_power_loss: root_stage_power_loss,
    root_commit_power_loss: root_commit_power_loss
  }
end

puts JSON.generate(run_loader_state_demo) if $PROGRAM_NAME == __FILE__
