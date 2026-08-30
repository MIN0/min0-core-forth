"""Digest-bound MIN0 CORE FORTH image envelope candidate R0."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping

from min0_core_forth_auth import ed25519_sign, ed25519_verify
from min0_core_forth_linker import (
    MANIFEST_FORMAT,
    MANIFEST_PROFILE,
    MANIFEST_VERSION,
    REFERENCE32_LIMIT,
    SECTIONS,
    LinkError,
    link_components,
)
from min0_core_forth_verify import BytecodeVerificationError, verify_image_bytecode


IMAGE_FORMAT = "min0-core-forth-image-envelope"
IMAGE_VERSION = 5
DIGEST_ALGORITHM = "sha256"
AUTHENTICATION_NONE = "none"
AUTHENTICATION_ED25519 = "ed25519"
MAX_GENERATION = (1 << 64) - 1
IMAGE_ROLE_NORMAL = "normal"
IMAGE_ROLE_RECOVERY = "recovery"
EXECUTION_PROFILE_SAFE_RUNTIME = "safe-runtime"
EXECUTION_PROFILE_STANDARD_BUILD = "standard-build"
KEY_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")


class ImageError(ValueError):
    pass


class ImageAuthenticationError(ImageError):
    pass


class ImageRollbackError(ImageError):
    pass


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ImageError(f"{label} must be an integer")
    return value


def _generation(value: object, label: str = "image generation") -> int:
    generation = _integer(value, label)
    if not 0 <= generation <= MAX_GENERATION:
        raise ImageError(f"{label} must be an unsigned 64-bit integer")
    return generation


def _key_id(value: object) -> str:
    if not isinstance(value, str) or KEY_ID_PATTERN.fullmatch(value) is None:
        raise ImageAuthenticationError(
            "authentication key_id must be 1..64 lowercase identifier characters"
        )
    return value


def _image_role(value: object) -> str:
    if value not in (IMAGE_ROLE_NORMAL, IMAGE_ROLE_RECOVERY):
        raise ImageError("image role must be normal or recovery")
    return value


def _execution_profile(value: object, label: str = "image execution profile") -> str:
    if value not in (
        EXECUTION_PROFILE_SAFE_RUNTIME,
        EXECUTION_PROFILE_STANDARD_BUILD,
    ):
        raise ImageError(f"{label} must be safe-runtime or standard-build")
    return value


def _required_execution_profile(verification: Mapping[str, object]) -> str:
    capabilities = verification.get("capabilities")
    if capabilities == []:
        return EXECUTION_PROFILE_SAFE_RUNTIME
    if capabilities == ["compiled-defer-store"]:
        return EXECUTION_PROFILE_STANDARD_BUILD
    raise ImageError("bytecode verifier returned unsupported capabilities")


def _check_execution_compatibility(
    image_profile: str,
    runtime_profile: str | None,
) -> None:
    if runtime_profile is None:
        return
    runtime = _execution_profile(runtime_profile, "loader execution profile")
    if (
        runtime == EXECUTION_PROFILE_SAFE_RUNTIME
        and image_profile != EXECUTION_PROFILE_SAFE_RUNTIME
    ):
        raise ImageError(
            f"image execution profile {image_profile} is incompatible with "
            f"loader profile {runtime}"
        )


def _signature(value: object) -> bytes:
    if (
        not isinstance(value, str)
        or len(value) != 128
        or value.lower() != value
    ):
        raise ImageAuthenticationError(
            "Ed25519 signature must be 64 bytes of lowercase hex"
        )
    try:
        return bytes.fromhex(value)
    except ValueError as exc:
        raise ImageAuthenticationError("Ed25519 signature hex is malformed") from exc


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifest_payload(manifest: Mapping[str, object]) -> bytes:
    records = manifest.get("records")
    if not isinstance(records, list):
        raise ImageError("manifest records must be a list")
    rows: list[list[object]] = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise ImageError(f"manifest record {index} must be a mapping")
        rows.append(
            [
                record.get("section"),
                record.get("offset"),
                record.get("target"),
                record.get("width"),
                record.get("kind"),
            ]
        )
    payload = [
        manifest.get("format"),
        manifest.get("version"),
        manifest.get("profile"),
        rows,
    ]
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()


def _identity_payload(envelope: Mapping[str, object]) -> bytes:
    descriptors = envelope.get("components")
    allocator = envelope.get("allocator")
    authentication = envelope.get("authentication")
    if not isinstance(descriptors, Mapping) or not isinstance(allocator, Mapping):
        raise ImageError("image identity metadata is malformed")
    if not isinstance(authentication, Mapping):
        raise ImageError("image authentication metadata is malformed")
    component_rows = []
    for section in SECTIONS:
        descriptor = descriptors.get(section)
        if not isinstance(descriptor, Mapping):
            raise ImageError(f"component descriptor {section} is malformed")
        component_rows.append(
            [
                section,
                descriptor.get("base"),
                descriptor.get("size"),
                descriptor.get("limit"),
                descriptor.get("sha256"),
            ]
        )
    payload = [
        envelope.get("format"),
        envelope.get("version"),
        envelope.get("profile"),
        envelope.get("digest_algorithm"),
        envelope.get("generation"),
        envelope.get("image_role"),
        envelope.get("execution_profile"),
        component_rows,
        [
            allocator.get("code_here"),
            allocator.get("header_here"),
            allocator.get("data_here"),
            allocator.get("latest"),
        ],
        envelope.get("manifest_sha256"),
        [authentication.get("scheme"), authentication.get("key_id")],
    ]
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()


def _validate_layout(
    images: dict[str, bytes],
    bases: dict[str, int],
    limits: dict[str, int],
    allocator: dict[str, int],
) -> None:
    ranges: list[tuple[int, int, str]] = []
    for section in SECTIONS:
        base = bases[section]
        limit = limits[section]
        if base < 0 or base >= REFERENCE32_LIMIT:
            raise ImageError(f"component {section} base is outside Reference32")
        if limit <= base or limit > REFERENCE32_LIMIT:
            raise ImageError(f"component {section} limit is invalid")
        if base + len(images[section]) > limit:
            raise ImageError(f"component {section} exceeds its region limit")
        ranges.append((base, limit, section))
    ranges.sort()
    for previous, current in zip(ranges, ranges[1:]):
        if current[0] < previous[1]:
            raise ImageError(
                f"component regions {previous[2]} and {current[2]} overlap"
            )
    expected_here = {
        "code_here": bases["code"] + len(images["code"]),
        "header_here": bases["dictionary"] + len(images["dictionary"]),
        "data_here": bases["data"] + len(images["data"]),
    }
    for name, expected in expected_here.items():
        if allocator[name] != expected:
            raise ImageError(f"allocator {name} disagrees with component length")
    latest = allocator["latest"]
    if latest and not (bases["dictionary"] <= latest < allocator["header_here"]):
        raise ImageError("allocator latest is outside used DICTIONARY")
    if latest % 4:
        raise ImageError("allocator latest is not cell-aligned")


def build_image_envelope(
    components: Mapping[str, object],
    bases: Mapping[str, int],
    limits: Mapping[str, int],
    allocator: Mapping[str, int],
    manifest: Mapping[str, object],
    *,
    generation: int,
    image_role: str = IMAGE_ROLE_NORMAL,
) -> dict:
    return _build_image_envelope(
        components,
        bases,
        limits,
        allocator,
        manifest,
        generation=generation,
        image_role=image_role,
        authentication={"scheme": AUTHENTICATION_NONE},
    )


def build_ed25519_image_envelope(
    components: Mapping[str, object],
    bases: Mapping[str, int],
    limits: Mapping[str, int],
    allocator: Mapping[str, int],
    manifest: Mapping[str, object],
    *,
    generation: int,
    key_id: str,
    private_key: object,
    image_role: str = IMAGE_ROLE_NORMAL,
) -> dict:
    normalized_key_id = _key_id(key_id)
    envelope = _build_image_envelope(
        components,
        bases,
        limits,
        allocator,
        manifest,
        generation=generation,
        image_role=image_role,
        authentication={
            "scheme": AUTHENTICATION_ED25519,
            "key_id": normalized_key_id,
        },
    )
    try:
        signature = ed25519_sign(envelope["identity_sha256"], private_key)
    except (TypeError, ValueError, AttributeError) as exc:
        raise ImageAuthenticationError("invalid Ed25519 private key") from exc
    envelope["authentication"]["signature_hex"] = signature.hex()
    return envelope


def _build_image_envelope(
    components: Mapping[str, object],
    bases: Mapping[str, int],
    limits: Mapping[str, int],
    allocator: Mapping[str, int],
    manifest: Mapping[str, object],
    *,
    generation: int,
    image_role: str,
    authentication: Mapping[str, object],
) -> dict:
    images: dict[str, bytes] = {}
    normalized_bases: dict[str, int] = {}
    normalized_limits: dict[str, int] = {}
    for section in SECTIONS:
        image = components.get(section)
        if not isinstance(image, (bytes, bytearray, memoryview)):
            raise ImageError(f"component {section} must be bytes")
        images[section] = bytes(image)
        normalized_bases[section] = _integer(bases.get(section), f"base {section}")
        normalized_limits[section] = _integer(limits.get(section), f"limit {section}")
    normalized_allocator = {
        name: _integer(allocator.get(name), f"allocator {name}")
        for name in ("code_here", "header_here", "data_here", "latest")
    }
    _validate_layout(
        images, normalized_bases, normalized_limits, normalized_allocator
    )
    manifest_copy = copy.deepcopy(dict(manifest))
    try:
        link_components(images, normalized_bases, normalized_bases, manifest_copy)
        code_verification = verify_image_bytecode(
            images, normalized_bases, manifest_copy
        )
    except (LinkError, BytecodeVerificationError) as exc:
        raise ImageError(f"image manifest is invalid: {exc}") from exc
    manifest_sha256 = _sha256(_manifest_payload(manifest_copy))
    normalized_generation = _generation(generation)
    normalized_role = _image_role(image_role)
    execution_profile = _required_execution_profile(code_verification)
    if (
        normalized_role == IMAGE_ROLE_RECOVERY
        and execution_profile != EXECUTION_PROFILE_SAFE_RUNTIME
    ):
        raise ImageError("recovery image must use safe-runtime execution profile")
    envelope = {
        "format": IMAGE_FORMAT,
        "version": IMAGE_VERSION,
        "profile": MANIFEST_PROFILE,
        "digest_algorithm": DIGEST_ALGORITHM,
        "generation": normalized_generation,
        "image_role": normalized_role,
        "execution_profile": execution_profile,
        "components": {
            section: {
                "base": normalized_bases[section],
                "size": len(images[section]),
                "limit": normalized_limits[section],
                "sha256": _sha256(images[section]),
            }
            for section in SECTIONS
        },
        "allocator": normalized_allocator,
        "manifest": manifest_copy,
        "manifest_sha256": manifest_sha256,
        "authentication": dict(authentication),
    }
    envelope["identity_sha256"] = _sha256(_identity_payload(envelope))
    return envelope


def validate_image_envelope(
    components: Mapping[str, object],
    envelope: object,
    *,
    require_authentication: bool = False,
    minimum_generation: int = 0,
    trusted_public_keys: Mapping[str, object] | None = None,
    required_image_role: str | None = None,
    runtime_profile: str | None = None,
) -> dict:
    if not isinstance(envelope, Mapping):
        raise ImageError("image envelope must be a mapping")
    if set(envelope) != {
        "format", "version", "profile", "digest_algorithm", "generation",
        "image_role", "execution_profile", "components", "allocator", "manifest",
        "manifest_sha256", "authentication", "identity_sha256",
    }:
        raise ImageError("image envelope fields are malformed")
    if envelope.get("format") != IMAGE_FORMAT:
        raise ImageError("unsupported image envelope format")
    if _integer(envelope.get("version"), "image version") != IMAGE_VERSION:
        raise ImageError("unsupported image envelope version")
    if envelope.get("profile") != MANIFEST_PROFILE:
        raise ImageError("unsupported image profile")
    if envelope.get("digest_algorithm") != DIGEST_ALGORITHM:
        raise ImageError("unsupported image digest algorithm")
    generation = _generation(envelope.get("generation"))
    image_role = _image_role(envelope.get("image_role"))
    execution_profile = _execution_profile(envelope.get("execution_profile"))
    if required_image_role is not None and image_role != _image_role(required_image_role):
        raise ImageError(
            f"image role {image_role} does not satisfy required role {required_image_role}"
        )
    _check_execution_compatibility(execution_profile, runtime_profile)
    minimum = _generation(minimum_generation, "minimum generation")
    authentication = envelope.get("authentication")
    if not isinstance(authentication, Mapping):
        raise ImageError("image authentication metadata is malformed")
    scheme = authentication.get("scheme")
    key_id = None
    signature = None
    if scheme == AUTHENTICATION_NONE:
        if set(authentication) != {"scheme"}:
            raise ImageAuthenticationError(
                "none authentication block contains unexpected fields"
            )
    elif scheme == AUTHENTICATION_ED25519:
        if set(authentication) != {"scheme", "key_id", "signature_hex"}:
            raise ImageAuthenticationError("Ed25519 authentication block is malformed")
        key_id = _key_id(authentication.get("key_id"))
        signature = _signature(authentication.get("signature_hex"))
    else:
        raise ImageAuthenticationError("unsupported image authentication scheme")
    if require_authentication and scheme == AUTHENTICATION_NONE:
        raise ImageAuthenticationError("authenticated image is required")

    descriptors = envelope.get("components")
    allocator_raw = envelope.get("allocator")
    manifest = envelope.get("manifest")
    if not isinstance(descriptors, Mapping) or not isinstance(allocator_raw, Mapping):
        raise ImageError("image metadata is malformed")
    if not isinstance(manifest, Mapping):
        raise ImageError("image manifest is malformed")
    if set(descriptors) != set(SECTIONS):
        raise ImageError("image component descriptor fields are malformed")
    if set(allocator_raw) != {"code_here", "header_here", "data_here", "latest"}:
        raise ImageError("image allocator fields are malformed")
    images: dict[str, bytes] = {}
    bases: dict[str, int] = {}
    limits: dict[str, int] = {}
    for section in SECTIONS:
        image = components.get(section)
        descriptor = descriptors.get(section)
        if not isinstance(image, (bytes, bytearray, memoryview)):
            raise ImageError(f"component {section} must be bytes")
        if not isinstance(descriptor, Mapping):
            raise ImageError(f"component descriptor {section} is malformed")
        if set(descriptor) != {"base", "size", "limit", "sha256"}:
            raise ImageError(f"component descriptor {section} fields are malformed")
        images[section] = bytes(image)
        bases[section] = _integer(descriptor.get("base"), f"base {section}")
        limits[section] = _integer(descriptor.get("limit"), f"limit {section}")
        size = _integer(descriptor.get("size"), f"size {section}")
        if size != len(images[section]):
            raise ImageError(f"component {section} size mismatch")
        if descriptor.get("sha256") != _sha256(images[section]):
            raise ImageError(f"component {section} digest mismatch")
    allocator = {
        name: _integer(allocator_raw.get(name), f"allocator {name}")
        for name in ("code_here", "header_here", "data_here", "latest")
    }
    _validate_layout(images, bases, limits, allocator)
    if manifest.get("format") != MANIFEST_FORMAT:
        raise ImageError("image contains unsupported manifest format")
    if _integer(manifest.get("version"), "manifest version") != MANIFEST_VERSION:
        raise ImageError("image contains unsupported manifest version")
    try:
        link_components(images, bases, bases, manifest)
        code_verification = verify_image_bytecode(images, bases, manifest)
    except (LinkError, BytecodeVerificationError) as exc:
        raise ImageError(f"image manifest is invalid: {exc}") from exc
    derived_execution_profile = _required_execution_profile(code_verification)
    if execution_profile != derived_execution_profile:
        raise ImageError(
            "image execution profile disagrees with relocation requirements"
        )
    if (
        image_role == IMAGE_ROLE_RECOVERY
        and execution_profile != EXECUTION_PROFILE_SAFE_RUNTIME
    ):
        raise ImageError("recovery image must use safe-runtime execution profile")
    if envelope.get("manifest_sha256") != _sha256(_manifest_payload(manifest)):
        raise ImageError("manifest digest mismatch")
    if envelope.get("identity_sha256") != _sha256(_identity_payload(envelope)):
        raise ImageError("image identity digest mismatch")
    if scheme == AUTHENTICATION_ED25519:
        if not isinstance(trusted_public_keys, Mapping) or key_id not in trusted_public_keys:
            raise ImageAuthenticationError("authentication key_id is not trusted")
        public_key = trusted_public_keys[key_id]
        if not isinstance(public_key, (bytes, bytearray, memoryview)):
            raise ImageAuthenticationError("trusted Ed25519 public key must be bytes")
        if not ed25519_verify(
            envelope["identity_sha256"], bytes(public_key), signature
        ):
            raise ImageAuthenticationError("Ed25519 image signature is invalid")
    if generation < minimum:
        raise ImageRollbackError(
            f"image generation {generation} is below trusted minimum {minimum}"
        )
    return {
        "components": images,
        "bases": bases,
        "limits": limits,
        "allocator": allocator,
        "manifest": manifest,
        "generation": generation,
        "authentication": {"scheme": scheme, "key_id": key_id},
        "image_role": image_role,
        "execution_profile": execution_profile,
        "code_verification": code_verification,
    }


def link_image_envelope(
    components: Mapping[str, object],
    envelope: object,
    target_bases: Mapping[str, int],
    target_limits: Mapping[str, int],
    *,
    require_authentication: bool = False,
    minimum_generation: int = 0,
    trusted_public_keys: Mapping[str, object] | None = None,
    required_image_role: str | None = None,
    runtime_profile: str | None = None,
) -> tuple[dict[str, bytes], dict]:
    validated = validate_image_envelope(
        components,
        envelope,
        require_authentication=require_authentication,
        minimum_generation=minimum_generation,
        trusted_public_keys=trusted_public_keys,
        required_image_role=required_image_role,
        runtime_profile=runtime_profile,
    )
    if validated["authentication"]["scheme"] != AUTHENTICATION_NONE:
        raise ImageAuthenticationError(
            "authenticated image relocation requires build-host re-signing"
        )
    new_bases = {
        section: _integer(target_bases.get(section), f"target base {section}")
        for section in SECTIONS
    }
    new_limits = {
        section: _integer(target_limits.get(section), f"target limit {section}")
        for section in SECTIONS
    }
    linked = link_components(
        validated["components"],
        validated["bases"],
        new_bases,
        validated["manifest"],
    )
    old_allocator = validated["allocator"]
    new_allocator = {
        "code_here": new_bases["code"] + len(linked["code"]),
        "header_here": new_bases["dictionary"] + len(linked["dictionary"]),
        "data_here": new_bases["data"] + len(linked["data"]),
        "latest": (
            old_allocator["latest"]
            + new_bases["dictionary"]
            - validated["bases"]["dictionary"]
            if old_allocator["latest"]
            else 0
        ),
    }
    linked_envelope = build_image_envelope(
        linked,
        new_bases,
        new_limits,
        new_allocator,
        validated["manifest"],
        generation=validated["generation"],
        image_role=validated["image_role"],
    )
    return linked, linked_envelope
