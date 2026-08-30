"""Cross-signed root-policy chain and power-loss-safe state for MIN0 CORE FORTH."""

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
from min0_core_forth_install import SimulatedPowerLoss, TrustedGenerationJournal


ROOT_POLICY_FORMAT = "min0-core-forth-root-policy"
ROOT_POLICY_VERSION = 1
ROOT_POLICY_DOMAIN = b"MIN0-CORE-FORTH-ROOT-POLICY-R0\0"
ROOT_STATE_DOMAIN = b"MIN0-CORE-FORTH-ROOT-STATE-R0\0"
ROOT_POLICY_INSTALL_STEPS = (
    "erase-inactive-root-state",
    "write-root-policy-chain",
    "seal-root-state",
)
KEY_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")


class RootPolicyError(ValueError):
    pass


def _key_id(value: object) -> str:
    if not isinstance(value, str) or KEY_ID_PATTERN.fullmatch(value) is None:
        raise RootPolicyError("root key_id is malformed")
    return value


def _public_key(value: object) -> bytes:
    if not isinstance(value, str) or len(value) != 64 or value.lower() != value:
        raise RootPolicyError("root public key must be 32 bytes of lowercase hex")
    try:
        return bytes.fromhex(value)
    except ValueError as exc:
        raise RootPolicyError("root public key hex is malformed") from exc


def _signature(value: object) -> bytes:
    if not isinstance(value, str) or len(value) != 128 or value.lower() != value:
        raise RootPolicyError("root policy signature must be 64 bytes of lowercase hex")
    try:
        return bytes.fromhex(value)
    except ValueError as exc:
        raise RootPolicyError("root policy signature hex is malformed") from exc


def _normalize_roots(roots: object) -> list[dict[str, str]]:
    if not isinstance(roots, Sequence) or isinstance(roots, (str, bytes, bytearray)):
        raise RootPolicyError("root entries must be a sequence")
    normalized = []
    seen = set()
    for entry in roots:
        if not isinstance(entry, Mapping) or set(entry) != {
            "key_id",
            "public_key_hex",
            "status",
        }:
            raise RootPolicyError("root entry fields are malformed")
        key_id = _key_id(entry.get("key_id"))
        if key_id in seen:
            raise RootPolicyError("duplicate root key_id")
        seen.add(key_id)
        public_key = _public_key(entry.get("public_key_hex"))
        status = entry.get("status")
        if status not in ("active", "retired"):
            raise RootPolicyError("root status must be active or retired")
        normalized.append(
            {
                "key_id": key_id,
                "public_key_hex": public_key.hex(),
                "status": status,
            }
        )
    normalized.sort(key=lambda item: item["key_id"])
    if not any(entry["status"] == "active" for entry in normalized):
        raise RootPolicyError("root policy must retain an active root")
    return normalized


def _normalize_signatures(signatures: object) -> list[dict[str, str]]:
    if not isinstance(signatures, Sequence) or isinstance(
        signatures, (str, bytes, bytearray)
    ):
        raise RootPolicyError("root signatures must be a sequence")
    normalized = []
    seen = set()
    for entry in signatures:
        if not isinstance(entry, Mapping) or set(entry) != {
            "key_id",
            "signature_hex",
        }:
            raise RootPolicyError("root signature entry fields are malformed")
        key_id = _key_id(entry.get("key_id"))
        if key_id in seen:
            raise RootPolicyError("duplicate root signature key_id")
        seen.add(key_id)
        normalized.append(
            {
                "key_id": key_id,
                "signature_hex": _signature(entry.get("signature_hex")).hex(),
            }
        )
    return sorted(normalized, key=lambda item: item["key_id"])


def _payload(policy: Mapping[str, object]) -> bytes:
    roots = _normalize_roots(policy.get("roots"))
    rows = [
        [entry["key_id"], entry["public_key_hex"], entry["status"]]
        for entry in roots
    ]
    payload = [
        policy.get("format"),
        policy.get("version"),
        policy.get("epoch"),
        policy.get("previous_policy_sha256"),
        rows,
    ]
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()


def policy_digest(policy: Mapping[str, object]) -> str:
    return hashlib.sha256(_payload(policy)).hexdigest()


def _message(policy: Mapping[str, object]) -> bytes:
    return ROOT_POLICY_DOMAIN + bytes.fromhex(policy_digest(policy))


def _root_map(roots: Sequence[Mapping[str, str]], status: str | None = None) -> dict[str, bytes]:
    return {
        entry["key_id"]: bytes.fromhex(entry["public_key_hex"])
        for entry in roots
        if status is None or entry["status"] == status
    }


def build_root_policy(
    epoch: int,
    roots: Sequence[Mapping[str, object]],
    signer_private_keys: Mapping[str, object],
    *,
    previous_policy: Mapping[str, object] | None = None,
) -> dict:
    normalized_epoch = validate_generation(epoch, "root policy epoch")
    normalized_roots = _normalize_roots(roots)
    policy = {
        "format": ROOT_POLICY_FORMAT,
        "version": ROOT_POLICY_VERSION,
        "epoch": normalized_epoch,
        "previous_policy_sha256": (
            policy_digest(previous_policy) if previous_policy is not None else None
        ),
        "roots": normalized_roots,
        "signatures": [],
    }
    signatures = []
    for key_id in sorted(signer_private_keys):
        normalized_key_id = _key_id(key_id)
        try:
            signed = signer_private_keys[key_id].sign(_message(policy))
        except (TypeError, ValueError, AttributeError) as exc:
            raise RootPolicyError("invalid root signer private key") from exc
        signatures.append(
            {"key_id": normalized_key_id, "signature_hex": signed.hex()}
        )
    policy["signatures"] = signatures
    return policy


def _validate_policy_shape(policy: object) -> dict:
    if not isinstance(policy, Mapping):
        raise RootPolicyError("root policy must be a mapping")
    if policy.get("format") != ROOT_POLICY_FORMAT:
        raise RootPolicyError("unsupported root policy format")
    if policy.get("version") != ROOT_POLICY_VERSION:
        raise RootPolicyError("unsupported root policy version")
    epoch = validate_generation(policy.get("epoch"), "root policy epoch")
    previous = policy.get("previous_policy_sha256")
    if previous is not None and (
        not isinstance(previous, str)
        or len(previous) != 64
        or previous.lower() != previous
    ):
        raise RootPolicyError("previous root policy digest is malformed")
    if previous is not None:
        try:
            bytes.fromhex(previous)
        except ValueError as exc:
            raise RootPolicyError("previous root policy digest is malformed") from exc
    roots = _normalize_roots(policy.get("roots"))
    signatures = _normalize_signatures(policy.get("signatures"))
    return {
        "epoch": epoch,
        "previous_policy_sha256": previous,
        "roots": roots,
        "signatures": signatures,
        "digest": policy_digest(policy),
    }


def validate_root_policy_chain(
    policies: object,
    pinned_bootstrap_roots: Mapping[str, object],
    *,
    minimum_epoch: int = 0,
) -> dict:
    if not isinstance(policies, Sequence) or isinstance(
        policies, (str, bytes, bytearray)
    ) or not policies:
        raise RootPolicyError("root policy chain must be a nonempty sequence")
    pinned = {}
    for key_id, public_key in pinned_bootstrap_roots.items():
        normalized_key_id = _key_id(key_id)
        if not isinstance(public_key, (bytes, bytearray, memoryview)) or len(public_key) != 32:
            raise RootPolicyError("pinned bootstrap root must be 32 bytes")
        pinned[normalized_key_id] = bytes(public_key)
    previous = None
    for index, raw_policy in enumerate(policies):
        current = _validate_policy_shape(raw_policy)
        current_all = _root_map(current["roots"])
        current_active = _root_map(current["roots"], "active")
        if index == 0:
            if current["previous_policy_sha256"] is not None:
                raise RootPolicyError("bootstrap policy must not have a predecessor")
            if current_active != pinned or len(current["roots"]) != len(pinned):
                raise RootPolicyError("bootstrap policy disagrees with pinned roots")
            required_signers = set(pinned)
            verification_keys = pinned
        else:
            assert previous is not None
            if current["epoch"] != previous["epoch"] + 1:
                raise RootPolicyError("root policy epoch must increase by exactly one")
            if current["previous_policy_sha256"] != previous["digest"]:
                raise RootPolicyError("root policy chain digest mismatch")
            previous_all = _root_map(previous["roots"])
            previous_active = _root_map(previous["roots"], "active")
            for key_id, previous_key in previous_all.items():
                if key_id not in current_all or current_all[key_id] != previous_key:
                    raise RootPolicyError("root key removal or replacement is forbidden")
                previous_status = next(
                    entry["status"]
                    for entry in previous["roots"]
                    if entry["key_id"] == key_id
                )
                current_status = next(
                    entry["status"]
                    for entry in current["roots"]
                    if entry["key_id"] == key_id
                )
                if previous_status == "retired" and current_status != "retired":
                    raise RootPolicyError("retired root cannot be reactivated")
            required_signers = set(previous_active) | set(current_active)
            verification_keys = {**previous_all, **current_all}
        signatures = {entry["key_id"]: entry["signature_hex"] for entry in current["signatures"]}
        if set(signatures) != required_signers:
            raise RootPolicyError("root policy signatures do not match required signers")
        for key_id in sorted(required_signers):
            try:
                Ed25519PublicKey.from_public_bytes(verification_keys[key_id]).verify(
                    bytes.fromhex(signatures[key_id]), _message(raw_policy)
                )
            except (InvalidSignature, ValueError, KeyError) as exc:
                raise RootPolicyError("root policy signature is invalid") from exc
        previous = current
    assert previous is not None
    minimum = validate_generation(minimum_epoch, "minimum root policy epoch")
    if previous["epoch"] < minimum:
        raise RootPolicyError(
            f"root policy epoch {previous['epoch']} is below minimum {minimum}"
        )
    return previous


def active_root_keys(validated_policy: Mapping[str, object]) -> dict[str, bytes]:
    return _root_map(validated_policy["roots"], "active")


def _chain_checksum(chain: Sequence[Mapping[str, object]]) -> str:
    material = bytearray(ROOT_STATE_DOMAIN)
    for policy in chain:
        material.extend(bytes.fromhex(policy_digest(policy)))
        for signature in _normalize_signatures(policy.get("signatures")):
            material.extend(signature["key_id"].encode("ascii"))
            material.extend(bytes.fromhex(signature["signature_hex"]))
    return hashlib.sha256(material).hexdigest()


@dataclass
class RootStateSlot:
    chain: list[dict] | None = None
    checksum: str | None = None


class RootPolicyStore:
    def __init__(
        self,
        bootstrap_policy: Mapping[str, object],
        pinned_bootstrap_roots: Mapping[str, object],
    ) -> None:
        bootstrap = copy.deepcopy(dict(bootstrap_policy))
        validated = validate_root_policy_chain([bootstrap], pinned_bootstrap_roots)
        self.pinned_bootstrap_roots = pinned_bootstrap_roots
        self.slots = [
            RootStateSlot([bootstrap], _chain_checksum([bootstrap])),
            RootStateSlot(),
        ]
        self.minimum_epoch = TrustedGenerationJournal(validated["epoch"])

    def _valid(self) -> list[tuple[int, dict]]:
        result = []
        for index, slot in enumerate(self.slots):
            if slot.chain is None:
                continue
            try:
                if slot.checksum != _chain_checksum(slot.chain):
                    continue
                validated = validate_root_policy_chain(
                    slot.chain,
                    self.pinned_bootstrap_roots,
                    minimum_epoch=self.minimum_epoch.minimum_accepted,
                )
            except (RootPolicyError, KeyError, TypeError):
                continue
            result.append((index, validated))
        return result

    def current(self) -> tuple[int, dict, list[dict]]:
        valid = self._valid()
        if not valid:
            raise RootPolicyError("no valid root policy chain satisfies minimum epoch")
        index, validated = max(valid, key=lambda item: item[1]["epoch"])
        return index, validated, self.slots[index].chain

    @staticmethod
    def _power_cut(fail_after: str | None) -> Callable[[str], None]:
        def after(step: str) -> None:
            if step == fail_after:
                raise SimulatedPowerLoss(step)

        return after

    def install(
        self, policy: Mapping[str, object], *, fail_after: str | None = None
    ) -> int:
        after = self._power_cut(fail_after)
        current_index, _validated, chain = self.current()
        candidate_chain = copy.deepcopy(chain) + [copy.deepcopy(dict(policy))]
        validate_root_policy_chain(
            candidate_chain,
            self.pinned_bootstrap_roots,
            minimum_epoch=self.minimum_epoch.minimum_accepted,
        )
        target = 1 - current_index
        self.slots[target] = RootStateSlot()
        after(ROOT_POLICY_INSTALL_STEPS[0])
        self.slots[target].chain = candidate_chain
        after(ROOT_POLICY_INSTALL_STEPS[1])
        self.slots[target].checksum = _chain_checksum(candidate_chain)
        after(ROOT_POLICY_INSTALL_STEPS[2])
        return target

    def commit_current(self, *, fail_after: str | None = None) -> int:
        _index, validated, _chain = self.current()
        return self.minimum_epoch.commit(
            validated["epoch"], self._power_cut(fail_after)
        )
