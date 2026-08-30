"""Exercise cross-signed root rotation, ordering, rollback, and power loss."""

from __future__ import annotations

import copy
import json

from auth_comparison_demo import ED25519_TEST_SEED
from min0_core_forth_auth import ed25519_private_from_seed, ed25519_public_bytes
from min0_core_forth_image import IMAGE_ROLE_NORMAL
from min0_core_forth_install import SimulatedPowerLoss, TRUST_COMMIT_STEPS
from min0_core_forth_root import (
    ROOT_POLICY_INSTALL_STEPS,
    RootPolicyError,
    RootPolicyStore,
    active_root_keys,
    build_root_policy,
    policy_digest,
    validate_root_policy_chain,
)
from min0_core_forth_trust import TrustError, build_trust_bundle, validate_trust_bundle


OLD_ROOT_ID = "fixture-offline-root-01"
NEW_ROOT_ID = "fixture-offline-root-02"
# Public, deterministic test fixtures only. Never use these keys in deployment.
OLD_ROOT_TEST_SEED = bytes([0xC3] * 32)
NEW_ROOT_TEST_SEED = bytes([0xD4] * 32)
IMAGE_KEY_ID = "fixture-ed25519-01"


def _root_entry(key_id: str, public_key: bytes, status: str) -> dict:
    return {
        "key_id": key_id,
        "public_key_hex": public_key.hex(),
        "status": status,
    }


def _image_key_entry(public_key: bytes) -> dict:
    return {
        "key_id": IMAGE_KEY_ID,
        "role": IMAGE_ROLE_NORMAL,
        "public_key_hex": public_key.hex(),
        "status": "active",
    }


def _rejected(operation, errors=(RootPolicyError, TrustError)) -> bool:
    try:
        operation()
    except errors:
        return True
    return False


def run_demo(implementation: str = "python") -> dict:
    old_private = ed25519_private_from_seed(OLD_ROOT_TEST_SEED)
    new_private = ed25519_private_from_seed(NEW_ROOT_TEST_SEED)
    old_public = ed25519_public_bytes(old_private)
    new_public = ed25519_public_bytes(new_private)
    pinned = {OLD_ROOT_ID: old_public}

    roots1 = [_root_entry(OLD_ROOT_ID, old_public, "active")]
    roots2 = [
        _root_entry(OLD_ROOT_ID, old_public, "active"),
        _root_entry(NEW_ROOT_ID, new_public, "active"),
    ]
    roots3 = [
        _root_entry(OLD_ROOT_ID, old_public, "retired"),
        _root_entry(NEW_ROOT_ID, new_public, "active"),
    ]
    policy1 = build_root_policy(1, roots1, {OLD_ROOT_ID: old_private})
    policy2 = build_root_policy(
        2,
        roots2,
        {OLD_ROOT_ID: old_private, NEW_ROOT_ID: new_private},
        previous_policy=policy1,
    )
    policy3 = build_root_policy(
        3,
        roots3,
        {OLD_ROOT_ID: old_private, NEW_ROOT_ID: new_private},
        previous_policy=policy2,
    )
    policy4 = build_root_policy(
        4,
        roots3,
        {NEW_ROOT_ID: new_private},
        previous_policy=policy3,
    )
    validate_root_policy_chain([policy1, policy2, policy3, policy4], pinned)

    root_write_power_loss = {}
    for step in ROOT_POLICY_INSTALL_STEPS:
        store = RootPolicyStore(policy1, pinned)
        try:
            store.install(policy2, fail_after=step)
        except SimulatedPowerLoss:
            pass
        _slot, current, _chain = store.current()
        root_write_power_loss[step] = {
            "visible_epoch": current["epoch"],
            "minimum_epoch": store.minimum_epoch.minimum_accepted,
        }

    root_commit_power_loss = {}
    for step in TRUST_COMMIT_STEPS:
        store = RootPolicyStore(policy1, pinned)
        store.install(policy2)
        try:
            store.commit_current(fail_after=step)
        except SimulatedPowerLoss:
            pass
        _slot, current, _chain = store.current()
        root_commit_power_loss[step] = {
            "visible_epoch": current["epoch"],
            "minimum_epoch": store.minimum_epoch.minimum_accepted,
        }

    image_private = ed25519_private_from_seed(ED25519_TEST_SEED)
    image_public = ed25519_public_bytes(image_private)
    trust_keys = [_image_key_entry(image_public)]
    old_root_bundle = build_trust_bundle(
        1,
        trust_keys,
        root_key_id=OLD_ROOT_ID,
        root_private_key=old_private,
    )
    new_root_bundle = build_trust_bundle(
        2,
        trust_keys,
        root_key_id=NEW_ROOT_ID,
        root_private_key=new_private,
    )

    store = RootPolicyStore(policy1, pinned)
    store.install(policy2)
    store.commit_current()
    _slot, overlap, _chain = store.current()
    overlap_keys = active_root_keys(overlap)
    validate_trust_bundle(old_root_bundle, overlap_keys, minimum_epoch=1)
    validate_trust_bundle(new_root_bundle, overlap_keys, minimum_epoch=2)

    store.install(policy3)
    store.commit_current()
    _slot, retired, _chain = store.current()
    retired_keys = active_root_keys(retired)
    new_bundle_survives_retirement = not _rejected(
        lambda: validate_trust_bundle(
            new_root_bundle, retired_keys, minimum_epoch=2
        )
    )
    old_bundle_rejected_after_retirement = _rejected(
        lambda: validate_trust_bundle(
            old_root_bundle, retired_keys, minimum_epoch=1
        )
    )

    premature_store = RootPolicyStore(policy1, pinned)
    premature_store.install(policy2)
    premature_store.commit_current()
    premature_store.install(policy3)
    premature_store.commit_current()
    _slot, premature_policy, _chain = premature_store.current()
    premature_retirement_breaks_old_bundle = _rejected(
        lambda: validate_trust_bundle(
            old_root_bundle,
            active_root_keys(premature_policy),
            minimum_epoch=1,
        )
    )

    store.install(policy4)
    store.commit_current()
    _slot, final_policy, _chain = store.current()

    missing_new_signature = build_root_policy(
        2, roots2, {OLD_ROOT_ID: old_private}, previous_policy=policy1
    )
    missing_new_signature_rejected = _rejected(
        lambda: validate_root_policy_chain(
            [policy1, missing_new_signature], pinned
        )
    )
    tampered_signature = copy.deepcopy(policy2)
    tampered_signature["signatures"][0]["signature_hex"] = "00" * 64
    tampered_signature_rejected = _rejected(
        lambda: validate_root_policy_chain([policy1, tampered_signature], pinned)
    )
    broken_link = copy.deepcopy(policy2)
    broken_link["previous_policy_sha256"] = "00" * 32
    broken_link_rejected = _rejected(
        lambda: validate_root_policy_chain([policy1, broken_link], pinned)
    )
    replacement_roots = [
        _root_entry(OLD_ROOT_ID, new_public, "active"),
        _root_entry(NEW_ROOT_ID, new_public, "active"),
    ]
    replacement = build_root_policy(
        2,
        replacement_roots,
        {OLD_ROOT_ID: old_private, NEW_ROOT_ID: new_private},
        previous_policy=policy1,
    )
    root_replacement_rejected = _rejected(
        lambda: validate_root_policy_chain([policy1, replacement], pinned)
    )
    reactivated = build_root_policy(
        4,
        roots2,
        {OLD_ROOT_ID: old_private, NEW_ROOT_ID: new_private},
        previous_policy=policy3,
    )
    retired_reactivation_rejected = _rejected(
        lambda: validate_root_policy_chain(
            [policy1, policy2, policy3, reactivated], pinned
        )
    )
    root_rollback_rejected = _rejected(lambda: store.install(policy2))

    corrupt_store = RootPolicyStore(policy1, pinned)
    corrupt_store.install(policy2)
    corrupt_store.commit_current()
    current_slot, _validated, _chain = corrupt_store.current()
    corrupt_store.slots[current_slot].chain[-1]["epoch"] = 99
    corrupted_committed_chain_fails_closed = _rejected(corrupt_store.current)

    return {
        "implementation": implementation,
        "root_policy_format_version": policy4["version"],
        "root_public_keys": {
            "old": old_public.hex(),
            "new": new_public.hex(),
        },
        "policy_digests": {
            str(epoch): policy_digest(policy)
            for epoch, policy in enumerate(
                (policy1, policy2, policy3, policy4), start=1
            )
        },
        "policy_signatures": {
            str(epoch): {
                entry["key_id"]: entry["signature_hex"]
                for entry in policy["signatures"]
            }
            for epoch, policy in enumerate(
                (policy1, policy2, policy3, policy4), start=1
            )
        },
        "root_write_power_loss": root_write_power_loss,
        "root_commit_power_loss": root_commit_power_loss,
        "ordering": {
            "overlap_accepts_old_and_new_bundles": True,
            "new_bundle_survives_retirement": new_bundle_survives_retirement,
            "old_bundle_rejected_after_retirement": old_bundle_rejected_after_retirement,
            "premature_retirement_breaks_old_bundle": premature_retirement_breaks_old_bundle,
            "post_retirement_new_root_only_policy": final_policy["epoch"] == 4,
        },
        "rejected": {
            "missing_new_signature": missing_new_signature_rejected,
            "tampered_signature": tampered_signature_rejected,
            "broken_chain_link": broken_link_rejected,
            "root_key_replacement": root_replacement_rejected,
            "retired_root_reactivation": retired_reactivation_rejected,
            "root_policy_rollback": root_rollback_rejected,
            "corrupted_committed_chain_fails_closed": corrupted_committed_chain_fails_closed,
        },
        "final_root_epoch": store.minimum_epoch.minimum_accepted,
        "final_active_roots": sorted(active_root_keys(final_policy)),
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))
