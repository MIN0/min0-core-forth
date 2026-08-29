"""Independent recovery boot and normal-slot repair model for MIN0 CORE FORTH."""

from __future__ import annotations

import copy
from collections.abc import Mapping

from min0_core_forth_image import IMAGE_ROLE_RECOVERY, ImageError, validate_image_envelope
from min0_core_forth_install import (
    BootError,
    InstallError,
    TransactionalInstaller,
    TrustedGenerationJournal,
)


class ProtectedRecoveryStore:
    """Provisioned recovery image with a generation journal independent of normal."""

    def __init__(
        self,
        components: Mapping[str, bytes],
        envelope: Mapping[str, object],
        trusted_generation: int,
    ) -> None:
        self.components = {
            name: bytes(components[name]) for name in ("code", "dictionary", "data")
        }
        self.envelope = copy.deepcopy(dict(envelope))
        self.trusted = TrustedGenerationJournal(trusted_generation)


class RecoveryBootManager:
    def __init__(
        self,
        normal_installer: TransactionalInstaller,
        recovery_store: ProtectedRecoveryStore,
        recovery_public_keys: Mapping[str, object],
    ) -> None:
        self.normal_installer = normal_installer
        self.recovery_store = recovery_store
        self.recovery_public_keys = recovery_public_keys

    def select_boot(self) -> dict:
        try:
            normal = self.normal_installer.select_boot()
        except BootError:
            normal = None
        if normal is not None:
            return {"mode": "normal", **normal}
        try:
            validated = validate_image_envelope(
                self.recovery_store.components,
                self.recovery_store.envelope,
                require_authentication=True,
                minimum_generation=self.recovery_store.trusted.minimum_accepted,
                trusted_public_keys=self.recovery_public_keys,
                required_image_role=IMAGE_ROLE_RECOVERY,
            )
        except ImageError as exc:
            raise BootError("normal and recovery boot both failed") from exc
        return {
            "mode": "recovery",
            "slot": "R",
            "generation": validated["generation"],
            "identity": self.recovery_store.envelope["identity_sha256"],
            "trusted_generation": self.recovery_store.trusted.minimum_accepted,
        }

    def repair_normal(
        self,
        components: Mapping[str, bytes],
        envelope: Mapping[str, object],
        *,
        target_slot: str,
        fail_after: str | None = None,
    ) -> str:
        if self.select_boot()["mode"] != "recovery":
            raise InstallError("normal repair is allowed only from recovery mode")
        return self.normal_installer.repair_install(
            components,
            envelope,
            target_slot=target_slot,
            fail_after=fail_after,
        )
