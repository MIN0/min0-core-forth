"""Exercise the integrated persistent-package loader update state machine."""

from __future__ import annotations

import copy
import json

from auth_comparison_demo import ED25519_TEST_SEED
from min0_core_forth_auth import ed25519_private_from_seed, ed25519_public_bytes
from min0_core_forth_image import IMAGE_ROLE_NORMAL, IMAGE_ROLE_RECOVERY
from min0_core_forth_install import SimulatedPowerLoss, TRUST_COMMIT_STEPS
from min0_core_forth_loader import Min0CoreForthLoader, LoaderError, LoaderOrderError
from min0_core_forth_persistent import (
    encode_image_package,
    encode_root_policy_chain_package,
    encode_trust_bundle_package,
)
from min0_core_forth_root import ROOT_POLICY_INSTALL_STEPS, RootPolicyError, build_root_policy
from min0_core_forth_trust import TrustError, build_trust_bundle
from recovery_path_demo import RECOVERY_KEY_ID, RECOVERY_TEST_SEED
from root_rotation_demo import (
    NEW_ROOT_ID,
    NEW_ROOT_TEST_SEED,
    OLD_ROOT_ID,
    OLD_ROOT_TEST_SEED,
)
from signed_image_demo import KEY_ID
from trust_rotation_demo import (
    NORMAL_KEY2_ID,
    NORMAL_KEY2_TEST_SEED,
    RECOVERY_KEY2_ID,
    RECOVERY_KEY2_TEST_SEED,
    _signed_image,
)


def _root_entry(key_id: str, public_key: bytes, status: str) -> dict:
    return {
        "key_id": key_id,
        "public_key_hex": public_key.hex(),
        "status": status,
    }


def _trust_entry(key_id: str, role: str, public_key: bytes, status: str) -> dict:
    return {
        "key_id": key_id,
        "role": role,
        "public_key_hex": public_key.hex(),
        "status": status,
    }


def _rejected(operation) -> bool:
    try:
        operation()
    except (
        LoaderError,
        LoaderOrderError,
        RootPolicyError,
        TrustError,
        ValueError,
    ):
        return True
    return False


def _fixtures() -> dict:
    old_root_private = ed25519_private_from_seed(OLD_ROOT_TEST_SEED)
    new_root_private = ed25519_private_from_seed(NEW_ROOT_TEST_SEED)
    old_root_public = ed25519_public_bytes(old_root_private)
    new_root_public = ed25519_public_bytes(new_root_private)
    old_normal_private = ed25519_private_from_seed(ED25519_TEST_SEED)
    new_normal_private = ed25519_private_from_seed(NORMAL_KEY2_TEST_SEED)
    old_recovery_private = ed25519_private_from_seed(RECOVERY_TEST_SEED)
    new_recovery_private = ed25519_private_from_seed(RECOVERY_KEY2_TEST_SEED)
    old_normal_public = ed25519_public_bytes(old_normal_private)
    new_normal_public = ed25519_public_bytes(new_normal_private)
    old_recovery_public = ed25519_public_bytes(old_recovery_private)
    new_recovery_public = ed25519_public_bytes(new_recovery_private)

    roots1 = [_root_entry(OLD_ROOT_ID, old_root_public, "active")]
    roots2 = [
        _root_entry(OLD_ROOT_ID, old_root_public, "active"),
        _root_entry(NEW_ROOT_ID, new_root_public, "active"),
    ]
    roots3 = [
        _root_entry(OLD_ROOT_ID, old_root_public, "retired"),
        _root_entry(NEW_ROOT_ID, new_root_public, "active"),
    ]
    policy1 = build_root_policy(1, roots1, {OLD_ROOT_ID: old_root_private})
    policy2 = build_root_policy(
        2,
        roots2,
        {OLD_ROOT_ID: old_root_private, NEW_ROOT_ID: new_root_private},
        previous_policy=policy1,
    )
    policy3 = build_root_policy(
        3,
        roots3,
        {OLD_ROOT_ID: old_root_private, NEW_ROOT_ID: new_root_private},
        previous_policy=policy2,
    )

    keys1 = [
        _trust_entry(KEY_ID, IMAGE_ROLE_NORMAL, old_normal_public, "active"),
        _trust_entry(
            RECOVERY_KEY_ID,
            IMAGE_ROLE_RECOVERY,
            old_recovery_public,
            "active",
        ),
    ]
    keys2 = keys1 + [
        _trust_entry(
            NORMAL_KEY2_ID, IMAGE_ROLE_NORMAL, new_normal_public, "active"
        ),
        _trust_entry(
            RECOVERY_KEY2_ID,
            IMAGE_ROLE_RECOVERY,
            new_recovery_public,
            "active",
        ),
    ]
    keys3 = [
        _trust_entry(KEY_ID, IMAGE_ROLE_NORMAL, old_normal_public, "revoked"),
        _trust_entry(
            NORMAL_KEY2_ID, IMAGE_ROLE_NORMAL, new_normal_public, "active"
        ),
        _trust_entry(
            RECOVERY_KEY_ID,
            IMAGE_ROLE_RECOVERY,
            old_recovery_public,
            "revoked",
        ),
        _trust_entry(
            RECOVERY_KEY2_ID,
            IMAGE_ROLE_RECOVERY,
            new_recovery_public,
            "active",
        ),
    ]
    bundle1 = build_trust_bundle(
        1,
        keys1,
        root_key_id=OLD_ROOT_ID,
        root_private_key=old_root_private,
    )
    bundle2 = build_trust_bundle(
        2,
        keys2,
        root_key_id=NEW_ROOT_ID,
        root_private_key=new_root_private,
    )
    bundle3 = build_trust_bundle(
        3,
        keys3,
        root_key_id=NEW_ROOT_ID,
        root_private_key=new_root_private,
    )
    normal1 = _signed_image(1, KEY_ID, old_normal_private, IMAGE_ROLE_NORMAL)
    normal2 = _signed_image(
        2, NORMAL_KEY2_ID, new_normal_private, IMAGE_ROLE_NORMAL
    )
    recovery1 = _signed_image(
        1, RECOVERY_KEY_ID, old_recovery_private, IMAGE_ROLE_RECOVERY
    )
    recovery2 = _signed_image(
        2, RECOVERY_KEY2_ID, new_recovery_private, IMAGE_ROLE_RECOVERY
    )
    return {
        "pinned": {OLD_ROOT_ID: old_root_public},
        "policies": (policy1, policy2, policy3),
        "bundles": (bundle1, bundle2, bundle3),
        "normal": (normal1, normal2),
        "recovery": (recovery1, recovery2),
        "packages": {
            "root2": encode_root_policy_chain_package([policy1, policy2]),
            "root3": encode_root_policy_chain_package([policy1, policy2, policy3]),
            "trust2": encode_trust_bundle_package(bundle2),
            "trust3": encode_trust_bundle_package(bundle3),
            "normal1": encode_image_package(*normal1),
            "normal2": encode_image_package(*normal2),
            "recovery2": encode_image_package(*recovery2),
        },
    }


def _loader(fixture: dict) -> Min0CoreForthLoader:
    policy1 = fixture["policies"][0]
    bundle1 = fixture["bundles"][0]
    normal1 = fixture["normal"][0]
    recovery1 = fixture["recovery"][0]
    return Min0CoreForthLoader(
        policy1,
        fixture["pinned"],
        bundle1,
        *normal1,
        *recovery1,
    )


def _advance_to_overlap(loader: Min0CoreForthLoader, packages: dict) -> None:
    loader.stage_root_package(packages["root2"])
    loader.commit_root()
    loader.stage_trust_package(packages["trust2"])
    loader.commit_trust()


def run_demo(implementation: str = "python") -> dict:
    fixture = _fixtures()
    packages = fixture["packages"]

    loader = _loader(fixture)
    initial = loader.status()
    _advance_to_overlap(loader, packages)
    normal_slot = loader.stage_image_package(
        packages["normal2"], role=IMAGE_ROLE_NORMAL
    )
    loader.commit_image(IMAGE_ROLE_NORMAL, normal_slot)
    recovery_slot = loader.stage_image_package(
        packages["recovery2"], role=IMAGE_ROLE_RECOVERY
    )
    loader.commit_image(IMAGE_ROLE_RECOVERY, recovery_slot)
    loader.stage_trust_package(packages["trust3"])
    loader.commit_trust()
    loader.stage_root_package(packages["root3"])
    loader.commit_root()
    final = loader.status()

    premature_root = _loader(fixture)
    premature_root.stage_root_package(packages["root2"])
    premature_root.commit_root()
    premature_root_retirement_rejected = _rejected(
        lambda: premature_root.stage_root_package(packages["root3"])
    )

    premature_trust = _loader(fixture)
    _advance_to_overlap(premature_trust, packages)
    premature_key_revocation_rejected = _rejected(
        lambda: premature_trust.stage_trust_package(packages["trust3"])
    )

    trust_before_root = _loader(fixture)
    new_root_bundle_before_overlap_rejected = _rejected(
        lambda: trust_before_root.stage_trust_package(packages["trust2"])
    )

    wrong_role = _loader(fixture)
    _advance_to_overlap(wrong_role, packages)
    role_confusion_rejected = _rejected(
        lambda: wrong_role.stage_image_package(
            packages["recovery2"], role=IMAGE_ROLE_NORMAL
        )
    )
    image_rollback_rejected = _rejected(
        lambda: wrong_role.stage_image_package(
            packages["normal1"], role=IMAGE_ROLE_NORMAL
        )
    )
    malformed_package_rejected = _rejected(
        lambda: wrong_role.stage_image_package(
            packages["normal2"][:-1], role=IMAGE_ROLE_NORMAL
        )
    )

    tampered_history = copy.deepcopy(fixture["policies"][0])
    tampered_history["epoch"] = 0
    history_package = encode_root_policy_chain_package(
        [tampered_history, fixture["policies"][1]]
    )
    root_history_mismatch_rejected = _rejected(
        lambda: _loader(fixture).stage_root_package(history_package)
    )

    failed_boot = _loader(fixture)
    _advance_to_overlap(failed_boot, packages)
    failed_slot = failed_boot.stage_image_package(
        packages["normal2"], role=IMAGE_ROLE_NORMAL
    )
    failed_boot.reject_image(IMAGE_ROLE_NORMAL, failed_slot)
    boot_failure_returns_old_generation = (
        failed_boot.status()["normal_generation"] == 1
        and failed_boot.phase() == "stable"
    )

    recovery_fallback = _loader(fixture)
    recovery_fallback.normal_store.slots["A"].marker = None
    recovery_status = recovery_fallback.status()
    all_normal_failure_selects_recovery = (
        recovery_status["phase"] == "stable"
        and recovery_status["normal_generation"] is None
        and recovery_status["boot"]["mode"] == "recovery"
        and recovery_status["boot"]["generation"] == 1
    )

    root_stage_power_loss = {}
    for step in ROOT_POLICY_INSTALL_STEPS:
        cut_loader = _loader(fixture)
        try:
            cut_loader.stage_root_package(packages["root2"], fail_after=step)
        except SimulatedPowerLoss:
            pass
        state = cut_loader.status()
        root_stage_power_loss[step] = {
            "root_epoch": state["root_epoch"],
            "minimum_epoch": state["minimum_root_epoch"],
            "phase": state["phase"],
        }

    root_commit_power_loss = {}
    for step in TRUST_COMMIT_STEPS:
        cut_loader = _loader(fixture)
        cut_loader.stage_root_package(packages["root2"])
        try:
            cut_loader.commit_root(fail_after=step)
        except SimulatedPowerLoss:
            pass
        state = cut_loader.status()
        root_commit_power_loss[step] = {
            "root_epoch": state["root_epoch"],
            "minimum_epoch": state["minimum_root_epoch"],
            "phase": state["phase"],
        }

    return {
        "implementation": implementation,
        "initial": initial,
        "final": final,
        "history": loader.history,
        "ordering": {
            "premature_root_retirement_rejected": premature_root_retirement_rejected,
            "premature_key_revocation_rejected": premature_key_revocation_rejected,
            "new_root_bundle_before_overlap_rejected": new_root_bundle_before_overlap_rejected,
            "boot_failure_returns_old_generation": boot_failure_returns_old_generation,
            "all_normal_failure_selects_recovery": all_normal_failure_selects_recovery,
        },
        "rejected": {
            "role_confusion": role_confusion_rejected,
            "image_rollback": image_rollback_rejected,
            "malformed_package": malformed_package_rejected,
            "root_history_mismatch": root_history_mismatch_rejected,
        },
        "root_stage_power_loss": root_stage_power_loss,
        "root_commit_power_loss": root_commit_power_loss,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))
