"""Audit every durable A/B install step with simulated power loss."""

from __future__ import annotations

import json

from auth_comparison_demo import ED25519_TEST_SEED
from min0_core_forth_auth import ed25519_private_from_seed, ed25519_public_bytes
from min0_core_forth_image import ImageError
from min0_core_forth_install import (
    INSTALL_STEPS,
    TRUST_COMMIT_STEPS,
    BootError,
    PersistentABStore,
    SimulatedPowerLoss,
    TransactionalInstaller,
)
from image_envelope_demo import build_source_image
from signed_image_demo import KEY_ID, _signed_from_template


def _signed_image(generation: int) -> tuple[dict[str, bytes], dict]:
    components, template = build_source_image(generation)
    return components, _signed_from_template(components, template, KEY_ID)


def _fresh(
    old_components: dict[str, bytes],
    old_envelope: dict,
    trusted: dict[str, bytes],
) -> tuple[PersistentABStore, TransactionalInstaller]:
    store = PersistentABStore(old_components, old_envelope, 7)
    return store, TransactionalInstaller(store, trusted)


def run_demo(implementation: str = "python") -> dict:
    old_components, old_envelope = _signed_image(7)
    new_components, new_envelope = _signed_image(8)
    rollback_components, rollback_envelope = _signed_image(6)
    public_key = ed25519_public_bytes(
        ed25519_private_from_seed(ED25519_TEST_SEED)
    )
    trusted = {KEY_ID: public_key}

    install_power_loss = {}
    for step in INSTALL_STEPS:
        store, installer = _fresh(old_components, old_envelope, trusted)
        try:
            installer.install(new_components, new_envelope, fail_after=step)
        except SimulatedPowerLoss:
            pass
        boot = installer.select_boot()
        install_power_loss[step] = {
            "boot_generation": boot["generation"],
            "boot_slot": boot["slot"],
            "trusted_generation": store.trusted.minimum_accepted,
        }

    trust_power_loss = {}
    for step in TRUST_COMMIT_STEPS:
        store, installer = _fresh(old_components, old_envelope, trusted)
        new_slot = installer.install(new_components, new_envelope)
        try:
            installer.report_boot_success(new_slot, fail_after=step)
        except SimulatedPowerLoss:
            pass
        boot = installer.select_boot()
        trust_power_loss[step] = {
            "boot_generation": boot["generation"],
            "boot_slot": boot["slot"],
            "trusted_generation": store.trusted.minimum_accepted,
        }

    store, installer = _fresh(old_components, old_envelope, trusted)
    new_slot = installer.install(new_components, new_envelope)
    pending_boot = installer.select_boot()
    installer.report_boot_failure(new_slot)
    fallback_boot = installer.select_boot()

    store2, installer2 = _fresh(old_components, old_envelope, trusted)
    corrupted_slot = installer2.install(new_components, new_envelope)
    changed = bytearray(store2.slots[corrupted_slot].components["code"])
    changed[-1] ^= 1
    store2.slots[corrupted_slot].components["code"] = bytes(changed)
    corrupted_fallback = installer2.select_boot()

    store3, installer3 = _fresh(old_components, old_envelope, trusted)
    marker_slot = installer3.install(new_components, new_envelope)
    marker = store3.slots[marker_slot].marker
    assert marker is not None and marker.checksum is not None
    marker.checksum = ("0" if marker.checksum[0] != "0" else "1") + marker.checksum[1:]
    marker_fallback = installer3.select_boot()

    store4, installer4 = _fresh(old_components, old_envelope, trusted)
    rollback_rejected = False
    try:
        installer4.install(rollback_components, rollback_envelope)
    except ImageError:
        rollback_rejected = True
    unchanged_after_rollback = installer4.select_boot()

    store5, installer5 = _fresh(old_components, old_envelope, trusted)
    committed_slot = installer5.install(new_components, new_envelope)
    committed_generation = installer5.report_boot_success(committed_slot)
    newest_record_index = store5.trusted.current()[0]
    newest_record = store5.trusted.records[newest_record_index]
    assert newest_record is not None and newest_record.checksum is not None
    newest_record.checksum = (
        ("0" if newest_record.checksum[0] != "0" else "1")
        + newest_record.checksum[1:]
    )
    journal_fallback_generation = store5.trusted.minimum_accepted
    journal_fallback_boot = installer5.select_boot()

    store6, installer6 = _fresh(old_components, old_envelope, trusted)
    committed_slot2 = installer6.install(new_components, new_envelope)
    installer6.report_boot_success(committed_slot2)
    changed2 = bytearray(store6.slots[committed_slot2].components["code"])
    changed2[-1] ^= 1
    store6.slots[committed_slot2].components["code"] = bytes(changed2)
    recovery_required = False
    try:
        installer6.select_boot()
    except BootError:
        recovery_required = True

    return {
        "implementation": implementation,
        "install_steps": list(INSTALL_STEPS),
        "trust_commit_steps": list(TRUST_COMMIT_STEPS),
        "install_power_loss": install_power_loss,
        "trust_power_loss": trust_power_loss,
        "pending_boot": pending_boot,
        "failed_boot_fallback": fallback_boot,
        "corrupted_candidate_fallback": corrupted_fallback,
        "torn_marker_fallback": marker_fallback,
        "rollback_rejected": rollback_rejected,
        "unchanged_after_rollback": unchanged_after_rollback,
        "successful_commit_generation": committed_generation,
        "trusted_journal_corruption": {
            "fallback_generation": journal_fallback_generation,
            "boot_generation": journal_fallback_boot["generation"],
        },
        "post_commit_active_corruption_requires_recovery": recovery_required,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))
