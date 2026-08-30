"""Audit root-signed key rotation, revocation, and recovery-image update ordering."""

from __future__ import annotations

import copy
import json

from auth_comparison_demo import ED25519_TEST_SEED
from min0_core_forth_auth import ed25519_private_from_seed, ed25519_public_bytes
from min0_core_forth_image import IMAGE_ROLE_NORMAL, IMAGE_ROLE_RECOVERY, ImageError
from min0_core_forth_install import (
    INSTALL_STEPS,
    TRUST_COMMIT_STEPS,
    BootError,
    PersistentABStore,
    SimulatedPowerLoss,
    TransactionalInstaller,
)
from min0_core_forth_trust import (
    TRUST_BUNDLE_INSTALL_STEPS,
    TrustBundleStore,
    TrustError,
    active_keys,
    build_trust_bundle,
    validate_image_with_trust_bundle,
    validate_trust_bundle,
)
from image_envelope_demo import build_source_image
from recovery_path_demo import RECOVERY_KEY_ID, RECOVERY_TEST_SEED
from signed_image_demo import KEY_ID, _signed_from_template


ROOT_KEY_ID = "fixture-offline-root-01"
# Public, deterministic test fixtures only. Never use these keys in deployment.
ROOT_TEST_SEED = bytes([0xC3] * 32)
NORMAL_KEY2_ID = "fixture-ed25519-02"
NORMAL_KEY2_TEST_SEED = bytes([0xA6] * 32)
RECOVERY_KEY2_ID = "fixture-recovery-ed25519-02"
RECOVERY_KEY2_TEST_SEED = bytes([0xB7] * 32)


def _entry(key_id: str, role: str, public_key: bytes, status: str) -> dict:
    return {
        "key_id": key_id,
        "role": role,
        "public_key_hex": public_key.hex(),
        "status": status,
    }


def _signed_image(
    generation: int, key_id: str, private_key, role: str
) -> tuple[dict[str, bytes], dict]:
    components, template = build_source_image(generation)
    return components, _signed_from_template(
        components,
        template,
        key_id,
        private_key=private_key,
        image_role=role,
    )


def _rejected(operation, errors=(TrustError, ImageError, BootError)) -> bool:
    try:
        operation()
    except errors:
        return True
    return False


def run_demo(implementation: str = "python") -> dict:
    root_private = ed25519_private_from_seed(ROOT_TEST_SEED)
    root_public = ed25519_public_bytes(root_private)
    pinned_roots = {ROOT_KEY_ID: root_public}
    old_normal_private = ed25519_private_from_seed(ED25519_TEST_SEED)
    old_normal_public = ed25519_public_bytes(old_normal_private)
    new_normal_private = ed25519_private_from_seed(NORMAL_KEY2_TEST_SEED)
    new_normal_public = ed25519_public_bytes(new_normal_private)
    old_recovery_private = ed25519_private_from_seed(RECOVERY_TEST_SEED)
    old_recovery_public = ed25519_public_bytes(old_recovery_private)
    new_recovery_private = ed25519_private_from_seed(RECOVERY_KEY2_TEST_SEED)
    new_recovery_public = ed25519_public_bytes(new_recovery_private)

    epoch1_keys = [
        _entry(KEY_ID, IMAGE_ROLE_NORMAL, old_normal_public, "active"),
        _entry(RECOVERY_KEY_ID, IMAGE_ROLE_RECOVERY, old_recovery_public, "active"),
    ]
    epoch2_keys = [
        _entry(KEY_ID, IMAGE_ROLE_NORMAL, old_normal_public, "active"),
        _entry(NORMAL_KEY2_ID, IMAGE_ROLE_NORMAL, new_normal_public, "active"),
        _entry(RECOVERY_KEY_ID, IMAGE_ROLE_RECOVERY, old_recovery_public, "active"),
        _entry(RECOVERY_KEY2_ID, IMAGE_ROLE_RECOVERY, new_recovery_public, "active"),
    ]
    epoch3_keys = [
        _entry(KEY_ID, IMAGE_ROLE_NORMAL, old_normal_public, "revoked"),
        _entry(NORMAL_KEY2_ID, IMAGE_ROLE_NORMAL, new_normal_public, "active"),
        _entry(RECOVERY_KEY_ID, IMAGE_ROLE_RECOVERY, old_recovery_public, "active"),
        _entry(RECOVERY_KEY2_ID, IMAGE_ROLE_RECOVERY, new_recovery_public, "active"),
    ]
    epoch4_keys = [
        _entry(KEY_ID, IMAGE_ROLE_NORMAL, old_normal_public, "revoked"),
        _entry(NORMAL_KEY2_ID, IMAGE_ROLE_NORMAL, new_normal_public, "active"),
        _entry(RECOVERY_KEY_ID, IMAGE_ROLE_RECOVERY, old_recovery_public, "revoked"),
        _entry(RECOVERY_KEY2_ID, IMAGE_ROLE_RECOVERY, new_recovery_public, "active"),
    ]
    bundles = {
        epoch: build_trust_bundle(
            epoch,
            keys,
            root_key_id=ROOT_KEY_ID,
            root_private_key=root_private,
        )
        for epoch, keys in (
            (1, epoch1_keys),
            (2, epoch2_keys),
            (3, epoch3_keys),
            (4, epoch4_keys),
        )
    }

    bundle_power_loss = {}
    for step in TRUST_BUNDLE_INSTALL_STEPS:
        store = TrustBundleStore(bundles[1], pinned_roots)
        try:
            store.install(bundles[2], fail_after=step)
        except SimulatedPowerLoss:
            pass
        _index, current, _bundle = store.current()
        bundle_power_loss[step] = {
            "visible_epoch": current["epoch"],
            "minimum_epoch": store.minimum_epoch.minimum_accepted,
        }

    epoch_commit_power_loss = {}
    for step in TRUST_COMMIT_STEPS:
        store = TrustBundleStore(bundles[1], pinned_roots)
        store.install(bundles[2])
        try:
            store.commit_current(fail_after=step)
        except SimulatedPowerLoss:
            pass
        _index, current, _bundle = store.current()
        epoch_commit_power_loss[step] = {
            "visible_epoch": current["epoch"],
            "minimum_epoch": store.minimum_epoch.minimum_accepted,
        }

    old_normal_components, old_normal_envelope = _signed_image(
        8, KEY_ID, old_normal_private, IMAGE_ROLE_NORMAL
    )
    new_normal_components, new_normal_envelope = _signed_image(
        9, NORMAL_KEY2_ID, new_normal_private, IMAGE_ROLE_NORMAL
    )
    validate_image_with_trust_bundle(
        old_normal_components,
        old_normal_envelope,
        bundles[2],
        pinned_roots,
        role=IMAGE_ROLE_NORMAL,
        minimum_generation=8,
        minimum_trust_epoch=2,
    )
    validate_image_with_trust_bundle(
        new_normal_components,
        new_normal_envelope,
        bundles[2],
        pinned_roots,
        role=IMAGE_ROLE_NORMAL,
        minimum_generation=8,
        minimum_trust_epoch=2,
    )
    old_normal_revoked = _rejected(
        lambda: validate_image_with_trust_bundle(
            old_normal_components,
            old_normal_envelope,
            bundles[3],
            pinned_roots,
            role=IMAGE_ROLE_NORMAL,
            minimum_generation=8,
            minimum_trust_epoch=3,
        )
    )
    validate_image_with_trust_bundle(
        new_normal_components,
        new_normal_envelope,
        bundles[3],
        pinned_roots,
        role=IMAGE_ROLE_NORMAL,
        minimum_generation=8,
        minimum_trust_epoch=3,
    )

    old_recovery_components, old_recovery_envelope = _signed_image(
        1, RECOVERY_KEY_ID, old_recovery_private, IMAGE_ROLE_RECOVERY
    )
    new_recovery_components, new_recovery_envelope = _signed_image(
        2, RECOVERY_KEY2_ID, new_recovery_private, IMAGE_ROLE_RECOVERY
    )
    validated_epoch2 = validate_trust_bundle(
        bundles[2], pinned_roots, minimum_epoch=2
    )
    recovery_overlap_keys = active_keys(validated_epoch2, IMAGE_ROLE_RECOVERY)

    recovery_update_power_loss = {}
    for step in INSTALL_STEPS:
        recovery_store = PersistentABStore(
            old_recovery_components, old_recovery_envelope, 1
        )
        updater = TransactionalInstaller(
            recovery_store,
            recovery_overlap_keys,
            required_image_role=IMAGE_ROLE_RECOVERY,
        )
        try:
            updater.install(
                new_recovery_components, new_recovery_envelope, fail_after=step
            )
        except SimulatedPowerLoss:
            pass
        boot = updater.select_boot()
        recovery_update_power_loss[step] = {
            "generation": boot["generation"],
            "slot": boot["slot"],
            "minimum_generation": recovery_store.trusted.minimum_accepted,
        }

    recovery_store = PersistentABStore(
        old_recovery_components, old_recovery_envelope, 1
    )
    updater = TransactionalInstaller(
        recovery_store,
        recovery_overlap_keys,
        required_image_role=IMAGE_ROLE_RECOVERY,
    )
    new_recovery_slot = updater.install(
        new_recovery_components, new_recovery_envelope
    )
    updater.report_boot_success(new_recovery_slot)
    validated_epoch4 = validate_trust_bundle(
        bundles[4], pinned_roots, minimum_epoch=4
    )
    post_revoke_updater = TransactionalInstaller(
        recovery_store,
        active_keys(validated_epoch4, IMAGE_ROLE_RECOVERY),
        required_image_role=IMAGE_ROLE_RECOVERY,
    )
    post_revoke_recovery_boot = post_revoke_updater.select_boot()

    premature_store = PersistentABStore(
        old_recovery_components, old_recovery_envelope, 1
    )
    premature_updater = TransactionalInstaller(
        premature_store,
        active_keys(validated_epoch4, IMAGE_ROLE_RECOVERY),
        required_image_role=IMAGE_ROLE_RECOVERY,
    )
    premature_revoke_breaks_old_recovery = _rejected(
        premature_updater.select_boot, errors=(BootError,)
    )

    trust_store = TrustBundleStore(bundles[1], pinned_roots)
    for epoch in (2, 3, 4):
        trust_store.install(bundles[epoch])
        trust_store.commit_current()
    bundle_rollback_rejected = _rejected(
        lambda: trust_store.install(bundles[1])
    )

    attacker_private = ed25519_private_from_seed(bytes([0xEE] * 32))
    forged = build_trust_bundle(
        5,
        epoch4_keys,
        root_key_id=ROOT_KEY_ID,
        root_private_key=attacker_private,
    )
    forged_bundle_rejected = _rejected(
        lambda: validate_trust_bundle(forged, pinned_roots, minimum_epoch=4)
    )
    tampered = copy.deepcopy(bundles[4])
    tampered["keys"][0]["status"] = "active"
    tampered_bundle_rejected = _rejected(
        lambda: validate_trust_bundle(tampered, pinned_roots, minimum_epoch=4)
    )

    return {
        "implementation": implementation,
        "bundle_format_version": bundles[4]["version"],
        "root_public_key_hex": root_public.hex(),
        "bundle_signatures": {
            str(epoch): bundles[epoch]["signature"]["signature_hex"]
            for epoch in (1, 2, 3, 4)
        },
        "bundle_power_loss": bundle_power_loss,
        "epoch_commit_power_loss": epoch_commit_power_loss,
        "normal_rotation": {
            "overlap_accepts_old_and_new": True,
            "old_revoked_at_epoch3": old_normal_revoked,
            "new_survives_epoch3": True,
        },
        "recovery_update_power_loss": recovery_update_power_loss,
        "post_revoke_recovery_boot": post_revoke_recovery_boot,
        "ordering": {
            "premature_revoke_breaks_old_recovery": premature_revoke_breaks_old_recovery,
            "correct_order_keeps_new_recovery": post_revoke_recovery_boot["generation"] == 2,
        },
        "rejected": {
            "bundle_rollback": bundle_rollback_rejected,
            "forged_root_signature": forged_bundle_rejected,
            "tampered_bundle": tampered_bundle_rejected,
        },
        "final_trust_epoch": trust_store.minimum_epoch.minimum_accepted,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))
