"""Power-loss-injectable A/B image install model for MIN0 CORE FORTH."""

from __future__ import annotations

import copy
import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from min0_core_forth_generation import GenerationError, validate_generation
from min0_core_forth_image import (
    EXECUTION_PROFILE_SAFE_RUNTIME,
    IMAGE_ROLE_NORMAL,
    ImageError,
    validate_image_envelope,
)


TRUSTED_RECORD_DOMAIN = b"MIN0-CORE-FORTH-TRUSTED-GENERATION-R0\0"
SLOT_MARKER_DOMAIN = b"MIN0-CORE-FORTH-SLOT-COMPLETE-R0\0"
INSTALL_STEPS = (
    "erase-inactive-slot",
    "write-code",
    "write-dictionary",
    "write-data",
    "write-envelope",
    "verify-staged-image",
    "write-complete-marker-body",
    "seal-complete-marker",
)
TRUST_COMMIT_STEPS = (
    "erase-next-trusted-record",
    "write-next-trusted-record",
    "seal-next-trusted-record",
)


class InstallError(RuntimeError):
    pass


class BootError(InstallError):
    pass


class SimulatedPowerLoss(InstallError):
    def __init__(self, step: str) -> None:
        super().__init__(f"simulated power loss after {step}")
        self.step = step


def _trusted_checksum(sequence: int, generation: int) -> str:
    payload = TRUSTED_RECORD_DOMAIN + f"{sequence}:{generation}".encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _marker_checksum(slot_name: str, sequence: int, identity: str) -> str:
    payload = (
        SLOT_MARKER_DOMAIN
        + slot_name.encode("ascii")
        + b":"
        + str(sequence).encode("ascii")
        + b":"
        + identity.encode("ascii")
    )
    return hashlib.sha256(payload).hexdigest()


@dataclass
class TrustedRecord:
    sequence: int
    generation: int
    checksum: str | None = None


class TrustedGenerationJournal:
    """Two-record journal; a record becomes visible only after checksum sealing."""

    def __init__(self, generation: int) -> None:
        normalized = validate_generation(generation, "trusted generation")
        self.records: list[TrustedRecord | None] = [
            TrustedRecord(1, normalized, _trusted_checksum(1, normalized)),
            None,
        ]

    def _valid_records(self) -> list[tuple[int, TrustedRecord]]:
        valid: list[tuple[int, TrustedRecord]] = []
        for index, record in enumerate(self.records):
            if record is None:
                continue
            try:
                generation = validate_generation(record.generation)
            except GenerationError:
                continue
            if (
                not isinstance(record.sequence, int)
                or isinstance(record.sequence, bool)
                or record.sequence <= 0
                or record.checksum != _trusted_checksum(record.sequence, generation)
            ):
                continue
            valid.append((index, record))
        return valid

    def current(self) -> tuple[int, int, int]:
        valid = self._valid_records()
        if not valid:
            raise BootError("no valid trusted-generation record")
        index, record = max(valid, key=lambda item: item[1].sequence)
        return index, record.sequence, record.generation

    @property
    def minimum_accepted(self) -> int:
        return self.current()[2]

    def commit(
        self,
        generation: int,
        after_step: Callable[[str], None] | None = None,
    ) -> int:
        candidate = validate_generation(generation)
        current_index, sequence, current_generation = self.current()
        if candidate < current_generation:
            raise GenerationError(
                f"generation {candidate} is below trusted minimum {current_generation}"
            )
        if candidate == current_generation:
            return current_generation
        target_index = 1 - current_index
        self.records[target_index] = None
        if after_step:
            after_step(TRUST_COMMIT_STEPS[0])
        next_sequence = sequence + 1
        self.records[target_index] = TrustedRecord(next_sequence, candidate)
        if after_step:
            after_step(TRUST_COMMIT_STEPS[1])
        self.records[target_index].checksum = _trusted_checksum(
            next_sequence, candidate
        )
        if after_step:
            after_step(TRUST_COMMIT_STEPS[2])
        return self.minimum_accepted


@dataclass
class CompleteMarker:
    sequence: int
    identity: str
    checksum: str | None = None


@dataclass
class ImageSlot:
    components: dict[str, bytes] = field(default_factory=dict)
    envelope: dict | None = None
    marker: CompleteMarker | None = None


class PersistentABStore:
    def __init__(
        self,
        initial_components: Mapping[str, bytes],
        initial_envelope: Mapping[str, object],
        trusted_generation: int,
    ) -> None:
        self.slots = {"A": ImageSlot(), "B": ImageSlot()}
        self.trusted = TrustedGenerationJournal(trusted_generation)
        self._write_initial("A", initial_components, initial_envelope)

    def _write_initial(
        self,
        slot_name: str,
        components: Mapping[str, bytes],
        envelope: Mapping[str, object],
    ) -> None:
        identity = envelope.get("identity_sha256")
        if not isinstance(identity, str):
            raise InstallError("initial envelope identity is malformed")
        self.slots[slot_name] = ImageSlot(
            components={name: bytes(components[name]) for name in ("code", "dictionary", "data")},
            envelope=copy.deepcopy(dict(envelope)),
            marker=CompleteMarker(1, identity, _marker_checksum(slot_name, 1, identity)),
        )


class TransactionalInstaller:
    def __init__(
        self,
        store: PersistentABStore,
        trusted_public_keys: Mapping[str, object],
        required_image_role: str = IMAGE_ROLE_NORMAL,
        runtime_profile: str = EXECUTION_PROFILE_SAFE_RUNTIME,
    ) -> None:
        self.store = store
        self.trusted_public_keys = trusted_public_keys
        self.required_image_role = required_image_role
        self.runtime_profile = runtime_profile

    @staticmethod
    def _power_cut(fail_after: str | None) -> Callable[[str], None]:
        def after_step(step: str) -> None:
            if fail_after == step:
                raise SimulatedPowerLoss(step)

        return after_step

    def _marker_is_valid(self, slot_name: str, slot: ImageSlot) -> bool:
        marker = slot.marker
        envelope = slot.envelope
        if marker is None or not isinstance(envelope, Mapping):
            return False
        identity = envelope.get("identity_sha256")
        return (
            isinstance(marker.sequence, int)
            and not isinstance(marker.sequence, bool)
            and marker.sequence > 0
            and isinstance(identity, str)
            and len(identity) == 64
            and identity.lower() == identity
            and all(character in "0123456789abcdef" for character in identity)
            and marker.identity == identity
            and marker.checksum
            == _marker_checksum(slot_name, marker.sequence, marker.identity)
        )

    def select_boot(self) -> dict:
        minimum = self.store.trusted.minimum_accepted
        candidates = []
        for slot_name, slot in self.store.slots.items():
            if not self._marker_is_valid(slot_name, slot):
                continue
            try:
                validated = validate_image_envelope(
                    slot.components,
                    slot.envelope,
                    require_authentication=True,
                    minimum_generation=minimum,
                    trusted_public_keys=self.trusted_public_keys,
                    required_image_role=self.required_image_role,
                    runtime_profile=self.runtime_profile,
                )
            except ImageError:
                continue
            candidates.append(
                (
                    validated["generation"],
                    slot.marker.sequence,
                    slot_name,
                    slot.envelope["identity_sha256"],
                )
            )
        if not candidates:
            raise BootError("no complete authenticated slot satisfies policy")
        generation, sequence, slot_name, identity = max(candidates)
        return {
            "slot": slot_name,
            "generation": generation,
            "sequence": sequence,
            "identity": identity,
            "trusted_generation": minimum,
        }

    def install(
        self,
        components: Mapping[str, bytes],
        envelope: Mapping[str, object],
        *,
        fail_after: str | None = None,
    ) -> str:
        after_step = self._power_cut(fail_after)
        validate_image_envelope(
            components,
            envelope,
            require_authentication=True,
            minimum_generation=self.store.trusted.minimum_accepted,
            trusted_public_keys=self.trusted_public_keys,
            required_image_role=self.required_image_role,
            runtime_profile=self.runtime_profile,
        )
        active = self.select_boot()["slot"]
        inactive = "B" if active == "A" else "A"
        self._write_candidate(inactive, components, envelope, after_step)
        return inactive

    def repair_install(
        self,
        components: Mapping[str, bytes],
        envelope: Mapping[str, object],
        *,
        target_slot: str,
        fail_after: str | None = None,
    ) -> str:
        if target_slot not in self.store.slots:
            raise InstallError("repair target slot must be A or B")
        validate_image_envelope(
            components,
            envelope,
            require_authentication=True,
            minimum_generation=self.store.trusted.minimum_accepted,
            trusted_public_keys=self.trusted_public_keys,
            required_image_role=self.required_image_role,
            runtime_profile=self.runtime_profile,
        )
        self._write_candidate(
            target_slot, components, envelope, self._power_cut(fail_after)
        )
        return target_slot

    def _write_candidate(
        self,
        target_slot: str,
        components: Mapping[str, bytes],
        envelope: Mapping[str, object],
        after_step: Callable[[str], None],
    ) -> None:
        slot = ImageSlot()
        self.store.slots[target_slot] = slot
        after_step(INSTALL_STEPS[0])
        for index, section in enumerate(("code", "dictionary", "data"), start=1):
            image = components.get(section)
            if not isinstance(image, (bytes, bytearray, memoryview)):
                raise InstallError(f"component {section} must be bytes")
            slot.components[section] = bytes(image)
            after_step(INSTALL_STEPS[index])
        slot.envelope = copy.deepcopy(dict(envelope))
        after_step(INSTALL_STEPS[4])
        validate_image_envelope(
            slot.components,
            slot.envelope,
            require_authentication=True,
            minimum_generation=self.store.trusted.minimum_accepted,
            trusted_public_keys=self.trusted_public_keys,
            required_image_role=self.required_image_role,
            runtime_profile=self.runtime_profile,
        )
        after_step(INSTALL_STEPS[5])
        valid_sequences = [
            candidate.marker.sequence
            for name, candidate in self.store.slots.items()
            if self._marker_is_valid(name, candidate)
        ]
        sequence = max(valid_sequences, default=0) + 1
        identity = slot.envelope["identity_sha256"]
        slot.marker = CompleteMarker(sequence, identity)
        after_step(INSTALL_STEPS[6])
        slot.marker.checksum = _marker_checksum(target_slot, sequence, identity)
        after_step(INSTALL_STEPS[7])

    def report_boot_success(
        self, slot_name: str, *, fail_after: str | None = None
    ) -> int:
        selected = self.select_boot()
        if selected["slot"] != slot_name:
            raise InstallError("boot success does not describe the selected slot")
        return self.store.trusted.commit(
            selected["generation"], self._power_cut(fail_after)
        )

    def report_boot_failure(self, slot_name: str) -> None:
        selected = self.select_boot()
        if selected["slot"] != slot_name:
            raise InstallError("boot failure does not describe the selected slot")
        self.store.slots[slot_name].marker = None
