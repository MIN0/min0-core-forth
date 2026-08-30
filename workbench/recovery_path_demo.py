"""Audit independent recovery boot and power-loss-safe normal-slot repair."""

from __future__ import annotations

import copy
import json

from auth_comparison_demo import ED25519_TEST_SEED
from min0_core_forth_auth import ed25519_private_from_seed, ed25519_public_bytes
from min0_core_forth_image import IMAGE_ROLE_RECOVERY, ImageError
from min0_core_forth_install import (
    INSTALL_STEPS,
    BootError,
    InstallError,
    PersistentABStore,
    SimulatedPowerLoss,
    TransactionalInstaller,
)
from min0_core_forth_recovery import ProtectedRecoveryStore, RecoveryBootManager
from image_envelope_demo import build_source_image
from signed_image_demo import KEY_ID, _signed_from_template


RECOVERY_KEY_ID = "fixture-recovery-ed25519-01"
# Public, deterministic test fixture only. Never use this key in deployment.
RECOVERY_TEST_SEED = bytes([0x5A] * 32)


def _normal_image(generation: int) -> tuple[dict[str, bytes], dict]:
    components, template = build_source_image(generation)
    return components, _signed_from_template(components, template, KEY_ID)


def _recovery_image() -> tuple[dict[str, bytes], dict, bytes]:
    components, template = build_source_image(1)
    private_key = ed25519_private_from_seed(RECOVERY_TEST_SEED)
    envelope = _signed_from_template(
        components,
        template,
        RECOVERY_KEY_ID,
        private_key=private_key,
        image_role=IMAGE_ROLE_RECOVERY,
    )
    return components, envelope, ed25519_public_bytes(private_key)


def _failed_normal_state(
    normal_public_key: bytes,
) -> tuple[PersistentABStore, TransactionalInstaller]:
    old_components, old_envelope = _normal_image(7)
    new_components, new_envelope = _normal_image(8)
    store = PersistentABStore(old_components, old_envelope, 7)
    installer = TransactionalInstaller(store, {KEY_ID: normal_public_key})
    new_slot = installer.install(new_components, new_envelope)
    installer.report_boot_success(new_slot)
    changed = bytearray(store.slots[new_slot].components["code"])
    changed[-1] ^= 1
    store.slots[new_slot].components["code"] = bytes(changed)
    return store, installer


def _manager(
    normal_public_key: bytes,
    recovery_components: dict[str, bytes],
    recovery_envelope: dict,
    recovery_public_key: bytes,
) -> tuple[PersistentABStore, TransactionalInstaller, RecoveryBootManager]:
    store, installer = _failed_normal_state(normal_public_key)
    recovery_store = ProtectedRecoveryStore(
        recovery_components, recovery_envelope, 1
    )
    manager = RecoveryBootManager(
        installer, recovery_store, {RECOVERY_KEY_ID: recovery_public_key}
    )
    return store, installer, manager


def _rejected(operation, errors=(ImageError, InstallError)) -> bool:
    try:
        operation()
    except errors:
        return True
    return False


def run_demo(implementation: str = "python") -> dict:
    normal_public_key = ed25519_public_bytes(
        ed25519_private_from_seed(ED25519_TEST_SEED)
    )
    recovery_components, recovery_envelope, recovery_public_key = _recovery_image()
    repair_components, repair_envelope = _normal_image(8)
    old_components, old_envelope = _normal_image(7)

    store, installer, manager = _manager(
        normal_public_key,
        recovery_components,
        recovery_envelope,
        recovery_public_key,
    )
    recovery_boot = manager.select_boot()

    repair_power_loss = {}
    for step in INSTALL_STEPS:
        cut_store, _cut_installer, cut_manager = _manager(
            normal_public_key,
            recovery_components,
            recovery_envelope,
            recovery_public_key,
        )
        try:
            cut_manager.repair_normal(
                repair_components,
                repair_envelope,
                target_slot="B",
                fail_after=step,
            )
        except SimulatedPowerLoss:
            pass
        boot = cut_manager.select_boot()
        repair_power_loss[step] = {
            "mode": boot["mode"],
            "generation": boot["generation"],
            "normal_trusted_generation": cut_store.trusted.minimum_accepted,
        }

    repaired_slot = manager.repair_normal(
        repair_components, repair_envelope, target_slot="B"
    )
    repaired_boot = manager.select_boot()
    installer.report_boot_success(repaired_slot)

    store2, _installer2, manager2 = _manager(
        normal_public_key,
        recovery_components,
        recovery_envelope,
        recovery_public_key,
    )
    old_repair_rejected = _rejected(
        lambda: manager2.repair_normal(
            old_components, old_envelope, target_slot="B"
        )
    )

    normal_components, normal_envelope = _normal_image(8)
    wrong_recovery_store = ProtectedRecoveryStore(
        normal_components, normal_envelope, 1
    )
    wrong_role_manager = RecoveryBootManager(
        manager2.normal_installer,
        wrong_recovery_store,
        {KEY_ID: normal_public_key},
    )
    normal_as_recovery_rejected = _rejected(
        wrong_role_manager.select_boot, errors=(BootError,)
    )

    combined_installer = TransactionalInstaller(
        store2, {KEY_ID: normal_public_key, RECOVERY_KEY_ID: recovery_public_key}
    )
    recovery_as_normal_rejected = _rejected(
        lambda: combined_installer.repair_install(
            recovery_components,
            recovery_envelope,
            target_slot="B",
        )
    )

    tampered_recovery = copy.deepcopy(recovery_envelope)
    tampered_recovery["image_role"] = "normal"
    tampered_store = ProtectedRecoveryStore(
        recovery_components, tampered_recovery, 1
    )
    tampered_manager = RecoveryBootManager(
        manager2.normal_installer,
        tampered_store,
        {RECOVERY_KEY_ID: recovery_public_key},
    )
    role_tamper_rejected = _rejected(
        tampered_manager.select_boot, errors=(BootError,)
    )

    corrupt_recovery_components = dict(recovery_components)
    corrupt_code = bytearray(corrupt_recovery_components["code"])
    corrupt_code[-1] ^= 1
    corrupt_recovery_components["code"] = bytes(corrupt_code)
    corrupt_recovery_store = ProtectedRecoveryStore(
        corrupt_recovery_components, recovery_envelope, 1
    )
    corrupt_recovery_manager = RecoveryBootManager(
        manager2.normal_installer,
        corrupt_recovery_store,
        {RECOVERY_KEY_ID: recovery_public_key},
    )
    total_failure_visible = _rejected(
        corrupt_recovery_manager.select_boot, errors=(BootError,)
    )

    healthy_old_components, healthy_old_envelope = _normal_image(7)
    healthy_store = PersistentABStore(healthy_old_components, healthy_old_envelope, 7)
    healthy_installer = TransactionalInstaller(
        healthy_store, {KEY_ID: normal_public_key}
    )
    healthy_recovery_store = ProtectedRecoveryStore(
        recovery_components, recovery_envelope, 1
    )
    healthy_manager = RecoveryBootManager(
        healthy_installer,
        healthy_recovery_store,
        {RECOVERY_KEY_ID: recovery_public_key},
    )
    repair_outside_recovery_rejected = _rejected(
        lambda: healthy_manager.repair_normal(
            repair_components, repair_envelope, target_slot="B"
        )
    )

    return {
        "implementation": implementation,
        "format_version": recovery_envelope["version"],
        "recovery_identity": recovery_envelope["identity_sha256"],
        "recovery_role": recovery_envelope["image_role"],
        "recovery_boot": recovery_boot,
        "repair_steps": list(INSTALL_STEPS),
        "repair_power_loss": repair_power_loss,
        "repaired_boot": repaired_boot,
        "normal_trusted_after_repair": store.trusted.minimum_accepted,
        "separate_generations": {
            "normal": store.trusted.minimum_accepted,
            "recovery": manager.recovery_store.trusted.minimum_accepted,
        },
        "rejected": {
            "old_normal_repair": old_repair_rejected,
            "normal_as_recovery": normal_as_recovery_rejected,
            "recovery_as_normal": recovery_as_normal_rejected,
            "role_tamper": role_tamper_rejected,
            "repair_outside_recovery": repair_outside_recovery_rejected,
        },
        "corrupt_recovery_total_failure_visible": total_failure_visible,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))
