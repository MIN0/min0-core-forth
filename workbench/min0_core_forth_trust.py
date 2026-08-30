"""Root-signed, role-scoped key bundles with rollback-resistant host journaling."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from min0_core_forth_generation import validate_generation
from min0_core_forth_image import (
    AUTHENTICATION_ED25519,
    IMAGE_ROLE_NORMAL,
    IMAGE_ROLE_RECOVERY,
    validate_image_envelope,
)
from min0_core_forth_install import (
    SimulatedPowerLoss,
    TRUST_COMMIT_STEPS,
    TrustedGenerationJournal,
)


TRUST_BUNDLE_FORMAT = "min0-core-forth-trust-bundle"
TRUST_BUNDLE_VERSION = 1
TRUST_BUNDLE_DOMAIN = b"MIN0-CORE-FORTH-TRUST-BUNDLE-R0\0"
TRUST_SLOT_DOMAIN = b"MIN0-CORE-FORTH-TRUST-SLOT-R0\0"
TRUST_BUNDLE_INSTALL_STEPS = (
    "erase-inactive-trust-slot",
    "write-trust-bundle",
    "seal-trust-slot",
)
KEY_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")


class TrustError(ValueError):
    pass


def _field(mapping: Mapping[str, object], name: str):
    return mapping.get(name)


def _key_id(value: object, label: str = "key_id") -> str:
    if not isinstance(value, str) or KEY_ID_PATTERN.fullmatch(value) is None:
        raise TrustError(f"{label} is malformed")
    return value


def _role(value: object) -> str:
    if value not in (IMAGE_ROLE_NORMAL, IMAGE_ROLE_RECOVERY):
        raise TrustError("trust key role must be normal or recovery")
    return value


def _public_key(value: object) -> bytes:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value.lower() != value
    ):
        raise TrustError("trust public key must be 32 bytes of lowercase hex")
    try:
        result = bytes.fromhex(value)
    except ValueError as exc:
        raise TrustError("trust public key hex is malformed") from exc
    return result


def _signature(value: object) -> bytes:
    if (
        not isinstance(value, str)
        or len(value) != 128
        or value.lower() != value
    ):
        raise TrustError("trust signature must be 64 bytes of lowercase hex")
    try:
        return bytes.fromhex(value)
    except ValueError as exc:
        raise TrustError("trust signature hex is malformed") from exc


def _normalize_keys(keys: object) -> list[dict[str, str]]:
    if not isinstance(keys, Sequence) or isinstance(keys, (str, bytes, bytearray)):
        raise TrustError("trust keys must be a sequence")
    normalized = []
    seen = set()
    for entry in keys:
        if not isinstance(entry, Mapping):
            raise TrustError("trust key entry must be a mapping")
        if set(entry) != {"key_id", "role", "public_key_hex", "status"}:
            raise TrustError("trust key entry fields are malformed")
        key_id = _key_id(entry.get("key_id"))
        if key_id in seen:
            raise TrustError("duplicate trust key_id")
        seen.add(key_id)
        role = _role(entry.get("role"))
        public_key = _public_key(entry.get("public_key_hex"))
        status = entry.get("status")
        if status not in ("active", "revoked"):
            raise TrustError("trust key status must be active or revoked")
        normalized.append(
            {
                "key_id": key_id,
                "role": role,
                "public_key_hex": public_key.hex(),
                "status": status,
            }
        )
    return sorted(normalized, key=lambda item: item["key_id"])


def _payload(bundle: Mapping[str, object]) -> bytes:
    keys = _normalize_keys(bundle.get("keys"))
    rows = [
        [entry["key_id"], entry["role"], entry["public_key_hex"], entry["status"]]
        for entry in keys
    ]
    payload = [
        bundle.get("format"),
        bundle.get("version"),
        bundle.get("epoch"),
        bundle.get("root_key_id"),
        rows,
    ]
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()


def _message(bundle: Mapping[str, object]) -> bytes:
    return TRUST_BUNDLE_DOMAIN + hashlib.sha256(_payload(bundle)).digest()


def build_trust_bundle(
    epoch: int,
    keys: Sequence[Mapping[str, object]],
    *,
    root_key_id: str,
    root_private_key: object,
) -> dict:
    normalized_epoch = validate_generation(epoch, "trust epoch")
    normalized_root_id = _key_id(root_key_id, "root_key_id")
    bundle = {
        "format": TRUST_BUNDLE_FORMAT,
        "version": TRUST_BUNDLE_VERSION,
        "epoch": normalized_epoch,
        "root_key_id": normalized_root_id,
        "keys": _normalize_keys(keys),
        "signature": {"scheme": AUTHENTICATION_ED25519},
    }
    try:
        signature = root_private_key.sign(_message(bundle))
    except (TypeError, ValueError, AttributeError) as exc:
        raise TrustError("invalid trust root private key") from exc
    bundle["signature"]["signature_hex"] = signature.hex()
    return bundle


def validate_trust_bundle(
    bundle: object,
    pinned_root_keys: Mapping[str, object],
    *,
    minimum_epoch: int = 0,
) -> dict:
    if not isinstance(bundle, Mapping):
        raise TrustError("trust bundle must be a mapping")
    if bundle.get("format") != TRUST_BUNDLE_FORMAT:
        raise TrustError("unsupported trust bundle format")
    if bundle.get("version") != TRUST_BUNDLE_VERSION:
        raise TrustError("unsupported trust bundle version")
    epoch = validate_generation(bundle.get("epoch"), "trust epoch")
    minimum = validate_generation(minimum_epoch, "minimum trust epoch")
    if epoch < minimum:
        raise TrustError(f"trust epoch {epoch} is below minimum {minimum}")
    root_key_id = _key_id(bundle.get("root_key_id"), "root_key_id")
    keys = _normalize_keys(bundle.get("keys"))
    signature_block = bundle.get("signature")
    if not isinstance(signature_block, Mapping) or set(signature_block) != {
        "scheme",
        "signature_hex",
    }:
        raise TrustError("trust signature block is malformed")
    if signature_block.get("scheme") != AUTHENTICATION_ED25519:
        raise TrustError("unsupported trust signature scheme")
    signature = _signature(signature_block.get("signature_hex"))
    if root_key_id not in pinned_root_keys:
        raise TrustError("trust root key is not pinned")
    public_key = pinned_root_keys[root_key_id]
    if not isinstance(public_key, (bytes, bytearray, memoryview)):
        raise TrustError("pinned root public key must be bytes")
    public_key = bytes(public_key)
    if len(public_key) != 32:
        raise TrustError("pinned root public key must be 32 bytes")
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, _message(bundle))
    except (InvalidSignature, ValueError) as exc:
        raise TrustError("trust bundle root signature is invalid") from exc
    return {
        "epoch": epoch,
        "root_key_id": root_key_id,
        "keys": keys,
    }


def active_keys(validated_bundle: Mapping[str, object], role: str) -> dict[str, bytes]:
    required_role = _role(role)
    result = {}
    for entry in validated_bundle["keys"]:
        if entry["role"] == required_role and entry["status"] == "active":
            result[entry["key_id"]] = bytes.fromhex(entry["public_key_hex"])
    return result


def validate_image_with_trust_bundle(
    components: Mapping[str, object],
    envelope: object,
    bundle: object,
    pinned_root_keys: Mapping[str, object],
    *,
    role: str,
    minimum_generation: int,
    minimum_trust_epoch: int,
) -> dict:
    validated_bundle = validate_trust_bundle(
        bundle, pinned_root_keys, minimum_epoch=minimum_trust_epoch
    )
    return validate_image_envelope(
        components,
        envelope,
        require_authentication=True,
        minimum_generation=minimum_generation,
        trusted_public_keys=active_keys(validated_bundle, role),
        required_image_role=role,
    )


def _slot_checksum(bundle: Mapping[str, object]) -> str:
    signature = _signature(bundle["signature"]["signature_hex"])
    return hashlib.sha256(
        TRUST_SLOT_DOMAIN + hashlib.sha256(_payload(bundle)).digest() + signature
    ).hexdigest()


@dataclass
class TrustSlot:
    bundle: dict | None = None
    checksum: str | None = None


class TrustBundleStore:
    def __init__(
        self,
        initial_bundle: Mapping[str, object],
        pinned_root_keys: Mapping[str, object] | Callable[[], Mapping[str, object]],
    ) -> None:
        self.pinned_root_keys = pinned_root_keys
        validated = validate_trust_bundle(initial_bundle, self._root_keys())
        initial_copy = copy.deepcopy(dict(initial_bundle))
        self.slots = [TrustSlot(initial_copy, _slot_checksum(initial_copy)), TrustSlot()]
        self.minimum_epoch = TrustedGenerationJournal(validated["epoch"])

    def _root_keys(self) -> Mapping[str, object]:
        keys = self.pinned_root_keys() if callable(self.pinned_root_keys) else self.pinned_root_keys
        if not isinstance(keys, Mapping):
            raise TrustError("trust root key provider did not return a mapping")
        return keys

    def _valid(self) -> list[tuple[int, dict]]:
        result = []
        minimum = self.minimum_epoch.minimum_accepted
        for index, slot in enumerate(self.slots):
            if slot.bundle is None:
                continue
            try:
                if slot.checksum != _slot_checksum(slot.bundle):
                    continue
                validated = validate_trust_bundle(
                    slot.bundle, self._root_keys(), minimum_epoch=minimum
                )
            except (TrustError, KeyError, TypeError):
                continue
            result.append((index, validated))
        return result

    def current(self) -> tuple[int, dict, dict]:
        valid = self._valid()
        if not valid:
            raise TrustError("no valid trust bundle satisfies minimum epoch")
        index, validated = max(valid, key=lambda item: item[1]["epoch"])
        return index, validated, self.slots[index].bundle

    @staticmethod
    def _power_cut(fail_after: str | None) -> Callable[[str], None]:
        def after(step: str) -> None:
            if step == fail_after:
                raise SimulatedPowerLoss(step)

        return after

    def install(self, bundle: Mapping[str, object], *, fail_after: str | None = None) -> int:
        after = self._power_cut(fail_after)
        _current_index, current_validated, _current_bundle = self.current()
        candidate = validate_trust_bundle(
            bundle,
            self._root_keys(),
            minimum_epoch=self.minimum_epoch.minimum_accepted,
        )
        if candidate["epoch"] <= current_validated["epoch"]:
            raise TrustError("new trust bundle epoch must increase")
        target = 1 - self.current()[0]
        self.slots[target] = TrustSlot()
        after(TRUST_BUNDLE_INSTALL_STEPS[0])
        bundle_copy = copy.deepcopy(dict(bundle))
        self.slots[target].bundle = bundle_copy
        after(TRUST_BUNDLE_INSTALL_STEPS[1])
        self.slots[target].checksum = _slot_checksum(bundle_copy)
        after(TRUST_BUNDLE_INSTALL_STEPS[2])
        return target

    def commit_current(self, *, fail_after: str | None = None) -> int:
        _index, validated, _bundle = self.current()
        return self.minimum_epoch.commit(
            validated["epoch"], self._power_cut(fail_after)
        )
