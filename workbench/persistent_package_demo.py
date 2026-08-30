"""Round-trip a signed FORTH image through a bounded external file package."""

from __future__ import annotations

import hashlib
import json
import struct
import tempfile
import copy
from pathlib import Path

from auth_comparison_demo import ED25519_TEST_SEED
from constructor_image_fixture import make_system
from min0_core_forth_auth import ed25519_private_from_seed, ed25519_public_bytes
from min0_core_forth_image import IMAGE_ROLE_NORMAL, ImageError, validate_image_envelope
from min0_core_forth_outer import OuterInterpreter
from min0_core_forth_persistent import (
    DEFAULT_LIMITS,
    DIRECTORY_ENTRY,
    HEADER,
    PersistentFormatError,
    canonical_json_bytes,
    decode_image_package,
    decode_root_policy_chain_package,
    decode_trust_bundle_package,
    encode_image_package,
    encode_package,
    encode_root_policy_chain_package,
    encode_trust_bundle_package,
    read_image_file,
    write_image_file,
)
from min0_core_forth_root import (
    active_root_keys,
    build_root_policy,
    validate_root_policy_chain,
)
from min0_core_forth_trust import (
    TrustError,
    active_keys,
    build_trust_bundle,
    validate_trust_bundle,
)
from image_envelope_demo import build_source_image
from root_rotation_demo import (
    NEW_ROOT_ID,
    NEW_ROOT_TEST_SEED,
    OLD_ROOT_ID,
    OLD_ROOT_TEST_SEED,
)
from signed_image_demo import KEY_ID, _signed_from_template


EXECUTION_SOURCE = "0 CHOOSE 1 CHOOSE 0 SPIN SUM SKIP STEP READ-ANSWER SLOT-ADDR"


def _root_entry(key_id: str, public_key: bytes) -> dict:
    return {
        "key_id": key_id,
        "public_key_hex": public_key.hex(),
        "status": "active",
    }


def _rejected(operation, errors=(PersistentFormatError, ImageError, TrustError)) -> bool:
    try:
        operation()
    except errors:
        return True
    return False


def _reseal(raw: bytearray) -> bytes:
    raw[-32:] = hashlib.sha256(raw[:-32]).digest()
    return bytes(raw)


def _with_metadata(metadata: bytes, components: dict[str, bytes]) -> bytes:
    return encode_package(
        "image",
        {
            "envelope": metadata,
            "code": components["code"],
            "dictionary": components["dictionary"],
            "data": components["data"],
        },
    )


def _execute(components: dict[str, bytes], validated: dict) -> list[int]:
    vm, dictionary = make_system()
    allocator = validated["allocator"]
    vm.load(components["code"], validated["bases"]["code"])
    dictionary.load_images(
        components["dictionary"],
        latest=allocator["latest"],
        body_image=components["data"],
    )
    outer = OuterInterpreter(vm, dictionary, code_base=allocator["code_here"])
    return outer.interpret(EXECUTION_SOURCE)


def run_demo(implementation: str = "python") -> dict:
    image_private = ed25519_private_from_seed(ED25519_TEST_SEED)
    image_public = ed25519_public_bytes(image_private)
    source_components, unsigned = build_source_image(7)
    signed = _signed_from_template(
        source_components, unsigned, KEY_ID, private_key=image_private
    )

    old_private = ed25519_private_from_seed(OLD_ROOT_TEST_SEED)
    new_private = ed25519_private_from_seed(NEW_ROOT_TEST_SEED)
    old_public = ed25519_public_bytes(old_private)
    new_public = ed25519_public_bytes(new_private)
    pinned = {OLD_ROOT_ID: old_public}
    roots1 = [_root_entry(OLD_ROOT_ID, old_public)]
    roots2 = [
        _root_entry(OLD_ROOT_ID, old_public),
        _root_entry(NEW_ROOT_ID, new_public),
    ]
    policy1 = build_root_policy(1, roots1, {OLD_ROOT_ID: old_private})
    policy2 = build_root_policy(
        2,
        roots2,
        {OLD_ROOT_ID: old_private, NEW_ROOT_ID: new_private},
        previous_policy=policy1,
    )
    root_package = encode_root_policy_chain_package([policy1, policy2])
    loaded_chain = decode_root_policy_chain_package(root_package)
    validated_root = validate_root_policy_chain(loaded_chain, pinned, minimum_epoch=2)

    trust_entries = [
        {
            "key_id": KEY_ID,
            "role": IMAGE_ROLE_NORMAL,
            "public_key_hex": image_public.hex(),
            "status": "active",
        }
    ]
    trust_bundle = build_trust_bundle(
        2,
        trust_entries,
        root_key_id=NEW_ROOT_ID,
        root_private_key=new_private,
    )
    trust_package = encode_trust_bundle_package(trust_bundle)
    loaded_bundle = decode_trust_bundle_package(trust_package)
    validated_trust = validate_trust_bundle(
        loaded_bundle, active_root_keys(validated_root), minimum_epoch=2
    )
    trusted_image_keys = active_keys(validated_trust, IMAGE_ROLE_NORMAL)

    image_package = encode_image_package(source_components, signed)
    with tempfile.TemporaryDirectory(prefix="min0-core-forth-persistent-") as directory:
        image_path = Path(directory) / "signed-image.fcp"
        write_result = write_image_file(image_path, source_components, signed)
        loaded_components, loaded_envelope = read_image_file(image_path)
        validated_image = validate_image_envelope(
            loaded_components,
            loaded_envelope,
            require_authentication=True,
            minimum_generation=7,
            trusted_public_keys=trusted_image_keys,
            required_image_role=IMAGE_ROLE_NORMAL,
        )
        stack = _execute(loaded_components, validated_image)

        oversized_path = Path(directory) / "oversized.fcp"
        oversized_path.write_bytes(b"X" * (DEFAULT_LIMITS.max_file_bytes + 1))
        oversized_file_rejected_before_parse = _rejected(
            lambda: read_image_file(oversized_path)
        )

    truncated = image_package[:-1]
    trailing = image_package + b"\0"
    checksum_tamper = bytearray(image_package)
    checksum_tamper[-33] ^= 1

    declared_length_bomb = bytearray(image_package)
    struct.pack_into("<I", declared_length_bomb, 20, 0xFFFFFFFF)
    section_count_bomb = bytearray(image_package)
    struct.pack_into("<H", section_count_bomb, 12, 0xFFFF)
    unknown_version = bytearray(image_package)
    struct.pack_into("<H", unknown_version, 8, 99)
    unknown_kind = bytearray(image_package)
    struct.pack_into("<H", unknown_kind, 10, 99)

    duplicate_section = bytearray(image_package)
    duplicate_section[HEADER.size + DIRECTORY_ENTRY.size : HEADER.size + DIRECTORY_ENTRY.size + 16] = (
        b"envelope" + b"\0" * 8
    )
    duplicate_section = _reseal(duplicate_section)

    overlap = bytearray(image_package)
    second_entry = HEADER.size + DIRECTORY_ENTRY.size
    struct.pack_into("<I", overlap, second_entry + 16, 0)
    overlap = _reseal(overlap)

    section_length_bomb = bytearray(image_package)
    struct.pack_into("<I", section_length_bomb, second_entry + 20, 0xFFFFFFFF)
    section_length_bomb = _reseal(section_length_bomb)

    duplicate_json = _with_metadata(b'{"a":1,"a":2}', source_components)
    noncanonical_json = _with_metadata(b'{"a": 1}', source_components)
    deep_json = _with_metadata(
        (b"[" * 33) + b"0" + (b"]" * 33), source_components
    )
    long_integer_json = _with_metadata(b'{"a":123456789012345678901}', source_components)

    resealed_component_tamper = bytearray(image_package)
    _magic, _version, _kind, count, _flags, directory_size, _payload_size, _file_size, _reserved = HEADER.unpack_from(
        resealed_component_tamper
    )
    _name, _offset, envelope_length, _entry_flags, _entry_reserved = DIRECTORY_ENTRY.unpack_from(
        resealed_component_tamper, HEADER.size
    )
    code_start = HEADER.size + directory_size + envelope_length
    resealed_component_tamper[code_start] ^= 1
    resealed_component_tamper = _reseal(resealed_component_tamper)
    tampered_components, tampered_envelope = decode_image_package(
        resealed_component_tamper
    )
    resealed_container_passes_structure = True
    image_signature_rejects_resealed_tamper = _rejected(
        lambda: validate_image_envelope(
            tampered_components,
            tampered_envelope,
            require_authentication=True,
            trusted_public_keys=trusted_image_keys,
        ),
        errors=(ImageError,),
    )
    extra_metadata_envelope = copy.deepcopy(signed)
    extra_metadata_envelope["attacker-note"] = "not covered by image identity"
    extra_metadata_package = encode_image_package(
        source_components, extra_metadata_envelope
    )
    extra_metadata_components, extra_metadata_loaded = decode_image_package(
        extra_metadata_package
    )
    unknown_image_metadata_rejected = _rejected(
        lambda: validate_image_envelope(
            extra_metadata_components,
            extra_metadata_loaded,
            require_authentication=True,
            trusted_public_keys=trusted_image_keys,
        ),
        errors=(ImageError,),
    )

    rejected = {
        "truncated": _rejected(lambda: decode_image_package(truncated)),
        "trailing_data": _rejected(lambda: decode_image_package(trailing)),
        "checksum_tamper": _rejected(
            lambda: decode_image_package(bytes(checksum_tamper))
        ),
        "declared_length_bomb": _rejected(
            lambda: decode_image_package(bytes(declared_length_bomb))
        ),
        "section_count_bomb": _rejected(
            lambda: decode_image_package(bytes(section_count_bomb))
        ),
        "unknown_version": _rejected(
            lambda: decode_image_package(bytes(unknown_version))
        ),
        "unknown_kind": _rejected(
            lambda: decode_image_package(bytes(unknown_kind))
        ),
        "duplicate_section": _rejected(
            lambda: decode_image_package(duplicate_section)
        ),
        "overlapping_sections": _rejected(lambda: decode_image_package(overlap)),
        "section_length_bomb": _rejected(
            lambda: decode_image_package(section_length_bomb)
        ),
        "duplicate_json_key": _rejected(
            lambda: decode_image_package(duplicate_json)
        ),
        "noncanonical_json": _rejected(
            lambda: decode_image_package(noncanonical_json)
        ),
        "deep_json": _rejected(lambda: decode_image_package(deep_json)),
        "long_json_integer": _rejected(
            lambda: decode_image_package(long_integer_json)
        ),
        "oversized_file": oversized_file_rejected_before_parse,
    }

    return {
        "implementation": implementation,
        "format_version": 1,
        "limits": {
            "max_file_bytes": DEFAULT_LIMITS.max_file_bytes,
            "max_sections": DEFAULT_LIMITS.max_sections,
            "max_metadata_bytes": DEFAULT_LIMITS.max_metadata_bytes,
        },
        "packages": {
            "image": {
                "bytes": len(image_package),
                "sha256": hashlib.sha256(image_package).hexdigest(),
            },
            "trust_bundle": {
                "bytes": len(trust_package),
                "sha256": hashlib.sha256(trust_package).hexdigest(),
            },
            "root_policy_chain": {
                "bytes": len(root_package),
                "sha256": hashlib.sha256(root_package).hexdigest(),
            },
        },
        "external_file": {
            "write_bytes": write_result["bytes"],
            "write_sha256": write_result["sha256"],
            "identity": loaded_envelope["identity_sha256"],
            "generation": validated_image["generation"],
            "stack": stack,
        },
        "trust_chain": {
            "root_epoch": validated_root["epoch"],
            "trust_epoch": validated_trust["epoch"],
            "image_key_id": KEY_ID,
            "valid": True,
        },
        "layering": {
            "resealed_container_passes_structure": resealed_container_passes_structure,
            "image_signature_rejects_resealed_tamper": image_signature_rejects_resealed_tamper,
            "unknown_image_metadata_rejected": unknown_image_metadata_rejected,
        },
        "rejected": rejected,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))
