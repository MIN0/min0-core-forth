"""Integrated, order-checked update loader state machine for MIN0 CORE FORTH."""

from __future__ import annotations

from collections.abc import Mapping

from min0_core_forth_generation import validate_generation
from min0_core_forth_image import (
    EXECUTION_PROFILE_SAFE_RUNTIME,
    IMAGE_ROLE_NORMAL,
    IMAGE_ROLE_RECOVERY,
    ImageError,
    validate_image_envelope,
)
from min0_core_forth_install import BootError, InstallError, PersistentABStore, TransactionalInstaller
from min0_core_forth_persistent import (
    PersistentFormatError,
    canonical_json_bytes,
    decode_image_package,
    decode_root_policy_chain_package,
    decode_trust_bundle_package,
)
from min0_core_forth_root import (
    RootPolicyError,
    RootPolicyStore,
    active_root_keys,
    validate_root_policy_chain,
)
from min0_core_forth_trust import (
    TrustBundleStore,
    TrustError,
    active_keys,
    validate_trust_bundle,
)


class LoaderError(RuntimeError):
    pass


class LoaderOrderError(LoaderError):
    pass


class Min0CoreForthLoader:
    """Derive update state from sealed stores; no untrusted file chooses a phase."""

    def __init__(
        self,
        bootstrap_policy: Mapping[str, object],
        pinned_bootstrap_roots: Mapping[str, object],
        initial_trust_bundle: Mapping[str, object],
        normal_components: Mapping[str, bytes],
        normal_envelope: Mapping[str, object],
        recovery_components: Mapping[str, bytes],
        recovery_envelope: Mapping[str, object],
        *,
        runtime_profile: str = EXECUTION_PROFILE_SAFE_RUNTIME,
    ) -> None:
        self.runtime_profile = runtime_profile
        self.root_store = RootPolicyStore(
            bootstrap_policy, pinned_bootstrap_roots
        )
        self.trust_store = TrustBundleStore(
            initial_trust_bundle, self._active_root_keys
        )
        normal_generation = validate_generation(
            normal_envelope.get("generation"), "initial normal generation"
        )
        recovery_generation = validate_generation(
            recovery_envelope.get("generation"), "initial recovery generation"
        )
        self.normal_store = PersistentABStore(
            normal_components, normal_envelope, normal_generation
        )
        self.recovery_store = PersistentABStore(
            recovery_components, recovery_envelope, recovery_generation
        )
        self.history: list[dict[str, object]] = []
        self._validate_current_images()
        self._record("initialized")

    def _active_root_keys(self) -> dict[str, bytes]:
        _slot, validated, _chain = self.root_store.current()
        return active_root_keys(validated)

    def _current_trust(self) -> tuple[dict, dict]:
        _slot, validated, bundle = self.trust_store.current()
        return validated, bundle

    def _image_keys(self, role: str) -> dict[str, bytes]:
        validated, _bundle = self._current_trust()
        return active_keys(validated, role)

    def _store(self, role: str) -> PersistentABStore:
        if role == IMAGE_ROLE_NORMAL:
            return self.normal_store
        if role == IMAGE_ROLE_RECOVERY:
            return self.recovery_store
        raise LoaderOrderError("loader image role must be normal or recovery")

    def _installer(self, role: str) -> TransactionalInstaller:
        return TransactionalInstaller(
            self._store(role),
            self._image_keys(role),
            required_image_role=role,
            runtime_profile=self.runtime_profile,
        )

    def _selected_image(self, role: str) -> tuple[dict, Mapping[str, object]]:
        installer = self._installer(role)
        selected = installer.select_boot()
        slot = self._store(role).slots[selected["slot"]]
        if slot.envelope is None:
            raise LoaderError("selected image slot has no envelope")
        return selected, slot.envelope

    def _validate_current_images(self, validated_trust: Mapping[str, object] | None = None) -> None:
        if validated_trust is None:
            validated_trust, _bundle = self._current_trust()
        for role in (IMAGE_ROLE_NORMAL, IMAGE_ROLE_RECOVERY):
            selected, envelope = self._selected_image(role)
            slot = self._store(role).slots[selected["slot"]]
            validate_image_envelope(
                slot.components,
                envelope,
                require_authentication=True,
                minimum_generation=self._store(role).trusted.minimum_accepted,
                trusted_public_keys=active_keys(validated_trust, role),
                required_image_role=role,
                runtime_profile=self.runtime_profile,
            )

    def _pending_domains(self) -> list[str]:
        pending = []
        _slot, root, _chain = self.root_store.current()
        if root["epoch"] > self.root_store.minimum_epoch.minimum_accepted:
            pending.append("root")
        trust, _bundle = self._current_trust()
        if trust["epoch"] > self.trust_store.minimum_epoch.minimum_accepted:
            pending.append("trust")
        for role in (IMAGE_ROLE_NORMAL, IMAGE_ROLE_RECOVERY):
            try:
                selected = self._installer(role).select_boot()
            except BootError:
                if role == IMAGE_ROLE_NORMAL:
                    continue
                raise
            if selected["generation"] > self._store(role).trusted.minimum_accepted:
                pending.append(role)
        return pending

    def phase(self) -> str:
        pending = self._pending_domains()
        if not pending:
            return "stable"
        if len(pending) != 1:
            raise LoaderOrderError("multiple uncommitted loader domains are visible")
        return f"{pending[0]}-awaiting-commit"

    def status(self) -> dict[str, object]:
        _root_slot, root, _chain = self.root_store.current()
        trust, _bundle = self._current_trust()
        try:
            normal = self._installer(IMAGE_ROLE_NORMAL).select_boot()
        except BootError:
            normal = None
        recovery = self._installer(IMAGE_ROLE_RECOVERY).select_boot()
        boot = (
            {"mode": "normal", **normal}
            if normal is not None
            else {"mode": "recovery", **recovery}
        )
        return {
            "phase": self.phase(),
            "runtime_profile": self.runtime_profile,
            "root_epoch": root["epoch"],
            "minimum_root_epoch": self.root_store.minimum_epoch.minimum_accepted,
            "trust_epoch": trust["epoch"],
            "minimum_trust_epoch": self.trust_store.minimum_epoch.minimum_accepted,
            "normal_generation": normal["generation"] if normal is not None else None,
            "minimum_normal_generation": self.normal_store.trusted.minimum_accepted,
            "recovery_generation": recovery["generation"],
            "minimum_recovery_generation": self.recovery_store.trusted.minimum_accepted,
            "boot": boot,
        }

    def _record(self, action: str) -> None:
        self.history.append({"action": action, "phase": self.phase()})

    def _require_stable(self) -> None:
        if self.phase() != "stable":
            raise LoaderOrderError("finish or reject the visible transaction first")

    def stage_root_package(self, raw: object, *, fail_after: str | None = None) -> int:
        self._require_stable()
        candidate_chain = decode_root_policy_chain_package(raw)
        _slot, _current, current_chain = self.root_store.current()
        if len(candidate_chain) != len(current_chain) + 1:
            raise LoaderOrderError("root package must append exactly one policy")
        for saved, candidate in zip(current_chain, candidate_chain[:-1]):
            if canonical_json_bytes(saved) != canonical_json_bytes(candidate):
                raise LoaderOrderError("root package history does not match installed chain")
        validated_candidate = validate_root_policy_chain(
            candidate_chain,
            self.root_store.pinned_bootstrap_roots,
            minimum_epoch=self.root_store.minimum_epoch.minimum_accepted,
        )
        _trust, current_bundle = self._current_trust()
        validate_trust_bundle(
            current_bundle,
            active_root_keys(validated_candidate),
            minimum_epoch=self.trust_store.minimum_epoch.minimum_accepted,
        )
        self.root_store.install(candidate_chain[-1], fail_after=fail_after)
        self._record("stage-root")
        return validated_candidate["epoch"]

    def commit_root(self, *, fail_after: str | None = None) -> int:
        if self.phase() != "root-awaiting-commit":
            raise LoaderOrderError("no root policy is awaiting commit")
        _slot, root, _chain = self.root_store.current()
        _trust, bundle = self._current_trust()
        validate_trust_bundle(
            bundle,
            active_root_keys(root),
            minimum_epoch=self.trust_store.minimum_epoch.minimum_accepted,
        )
        committed = self.root_store.commit_current(fail_after=fail_after)
        self._record("commit-root")
        return committed

    def stage_trust_package(self, raw: object, *, fail_after: str | None = None) -> int:
        self._require_stable()
        bundle = decode_trust_bundle_package(raw)
        candidate = validate_trust_bundle(
            bundle,
            self._active_root_keys(),
            minimum_epoch=self.trust_store.minimum_epoch.minimum_accepted,
        )
        self._validate_current_images(candidate)
        self.trust_store.install(bundle, fail_after=fail_after)
        self._record("stage-trust")
        return candidate["epoch"]

    def commit_trust(self, *, fail_after: str | None = None) -> int:
        if self.phase() != "trust-awaiting-commit":
            raise LoaderOrderError("no trust bundle is awaiting commit")
        trust, _bundle = self._current_trust()
        self._validate_current_images(trust)
        committed = self.trust_store.commit_current(fail_after=fail_after)
        self._record("commit-trust")
        return committed

    def stage_image_package(
        self,
        raw: object,
        *,
        role: str,
        fail_after: str | None = None,
    ) -> str:
        self._require_stable()
        components, envelope = decode_image_package(raw)
        generation = validate_generation(envelope.get("generation"), "candidate image generation")
        if generation <= self._store(role).trusted.minimum_accepted:
            raise LoaderOrderError("candidate image generation must increase")
        slot = self._installer(role).install(
            components, envelope, fail_after=fail_after
        )
        self._record(f"stage-{role}")
        return slot

    def stage_normal_repair_package(
        self,
        raw: object,
        *,
        target_slot: str | None = None,
        fail_after: str | None = None,
    ) -> str:
        """Install a newer normal image when no normal slot can currently boot."""
        self._require_stable()
        if self.select_boot()["mode"] != "recovery":
            raise LoaderOrderError("normal repair requires recovery boot mode")
        components, envelope = decode_image_package(raw)
        generation = validate_generation(
            envelope.get("generation"), "candidate normal repair generation"
        )
        if generation <= self.normal_store.trusted.minimum_accepted:
            raise LoaderOrderError("normal repair generation must increase")
        if target_slot is None:
            empty = [
                name
                for name, slot in self.normal_store.slots.items()
                if slot.envelope is None
            ]
            target_slot = empty[0] if empty else "B"
        self._installer(IMAGE_ROLE_NORMAL).repair_install(
            components,
            envelope,
            target_slot=target_slot,
            fail_after=fail_after,
        )
        self._record("stage-normal")
        return target_slot

    def commit_image(
        self,
        role: str,
        slot: str,
        *,
        fail_after: str | None = None,
    ) -> int:
        if self.phase() != f"{role}-awaiting-commit":
            raise LoaderOrderError(f"no {role} image is awaiting commit")
        committed = self._installer(role).report_boot_success(
            slot, fail_after=fail_after
        )
        self._record(f"commit-{role}")
        return committed

    def reject_image(self, role: str, slot: str) -> None:
        if self.phase() != f"{role}-awaiting-commit":
            raise LoaderOrderError(f"no {role} image is awaiting rejection")
        self._installer(role).report_boot_failure(slot)
        self._record(f"reject-{role}")

    def select_boot(self) -> dict[str, object]:
        try:
            return {"mode": "normal", **self._installer(IMAGE_ROLE_NORMAL).select_boot()}
        except BootError:
            try:
                return {
                    "mode": "recovery",
                    **self._installer(IMAGE_ROLE_RECOVERY).select_boot(),
                }
            except BootError as exc:
                raise LoaderError("normal and recovery boot both failed") from exc
