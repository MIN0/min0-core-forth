"""Exercise the Ed25519 authentication block in image-envelope v3."""

from __future__ import annotations

import copy
import json

from auth_comparison_demo import ED25519_TEST_SEED, WRONG_ED25519_TEST_SEED
from min0_core_forth_auth import ed25519_private_from_seed, ed25519_public_bytes
from min0_core_forth_image import (
    IMAGE_ROLE_NORMAL,
    ImageError,
    build_ed25519_image_envelope,
    link_image_envelope,
    validate_image_envelope,
)
from image_envelope_demo import TARGET_BASES, TARGET_LIMITS, build_source_image


KEY_ID = "fixture-ed25519-01"


def _signed_from_template(
    components: dict[str, bytes],
    template: dict,
    key_id: str,
    *,
    private_key=None,
    image_role: str = IMAGE_ROLE_NORMAL,
) -> dict:
    if private_key is None:
        private_key = ed25519_private_from_seed(ED25519_TEST_SEED)
    return build_ed25519_image_envelope(
        components,
        {name: template["components"][name]["base"] for name in ("code", "dictionary", "data")},
        {name: template["components"][name]["limit"] for name in ("code", "dictionary", "data")},
        template["allocator"],
        template["manifest"],
        generation=template["generation"],
        key_id=key_id,
        private_key=private_key,
        image_role=image_role,
    )


def _rejected(name: str, operation) -> str:
    try:
        operation()
    except ImageError:
        return name
    raise AssertionError(f"{name} was accepted")


def run_demo(implementation: str = "python") -> dict:
    components, unsigned = build_source_image(7)
    signed = _signed_from_template(components, unsigned, KEY_ID)
    private_key = ed25519_private_from_seed(ED25519_TEST_SEED)
    public_key = ed25519_public_bytes(private_key)
    wrong_public_key = ed25519_public_bytes(
        ed25519_private_from_seed(WRONG_ED25519_TEST_SEED)
    )
    trusted = {KEY_ID: public_key}
    validated = validate_image_envelope(
        components,
        signed,
        require_authentication=True,
        minimum_generation=7,
        trusted_public_keys=trusted,
    )

    corrupted = dict(components)
    changed_code = bytearray(corrupted["code"])
    changed_code[-1] ^= 1
    corrupted["code"] = bytes(changed_code)

    signature_tamper = copy.deepcopy(signed)
    original = signature_tamper["authentication"]["signature_hex"]
    signature_tamper["authentication"]["signature_hex"] = (
        ("0" if original[0] != "0" else "1") + original[1:]
    )
    malformed_signature = copy.deepcopy(signed)
    malformed_signature["authentication"]["signature_hex"] = "00"
    key_id_tamper = copy.deepcopy(signed)
    key_id_tamper["authentication"]["key_id"] = "attacker-key"
    unknown_scheme = copy.deepcopy(signed)
    unknown_scheme["authentication"]["scheme"] = "unknown-signature"
    extra_authentication_field = copy.deepcopy(signed)
    extra_authentication_field["authentication"]["public_key_hex"] = public_key.hex()
    unknown_signed = _signed_from_template(components, unsigned, "unknown-key-01")

    rejected = [
        _rejected(
            "component-tamper",
            lambda: validate_image_envelope(
                corrupted, signed, trusted_public_keys=trusted
            ),
        ),
        _rejected(
            "signature-tamper",
            lambda: validate_image_envelope(
                components, signature_tamper, trusted_public_keys=trusted
            ),
        ),
        _rejected(
            "malformed-signature",
            lambda: validate_image_envelope(
                components, malformed_signature, trusted_public_keys=trusted
            ),
        ),
        _rejected(
            "key-id-tamper",
            lambda: validate_image_envelope(
                components, key_id_tamper, trusted_public_keys=trusted
            ),
        ),
        _rejected(
            "unknown-scheme",
            lambda: validate_image_envelope(
                components, unknown_scheme, trusted_public_keys=trusted
            ),
        ),
        _rejected(
            "extra-authentication-field",
            lambda: validate_image_envelope(
                components, extra_authentication_field, trusted_public_keys=trusted
            ),
        ),
        _rejected(
            "unknown-key",
            lambda: validate_image_envelope(
                components, unknown_signed, trusted_public_keys=trusted
            ),
        ),
        _rejected(
            "wrong-public-key",
            lambda: validate_image_envelope(
                components, signed, trusted_public_keys={KEY_ID: wrong_public_key}
            ),
        ),
        _rejected(
            "missing-trust-store",
            lambda: validate_image_envelope(components, signed),
        ),
        _rejected(
            "unsigned-secure-mode",
            lambda: validate_image_envelope(
                components, unsigned, require_authentication=True
            ),
        ),
        _rejected(
            "signed-rollback",
            lambda: validate_image_envelope(
                components,
                signed,
                minimum_generation=8,
                trusted_public_keys=trusted,
            ),
        ),
        _rejected(
            "signed-relocation-without-resigning",
            lambda: link_image_envelope(
                components,
                signed,
                TARGET_BASES,
                TARGET_LIMITS,
                trusted_public_keys=trusted,
            ),
        ),
    ]

    linked, linked_unsigned = link_image_envelope(
        components, unsigned, TARGET_BASES, TARGET_LIMITS
    )
    linked_signed = _signed_from_template(linked, linked_unsigned, KEY_ID)
    validate_image_envelope(
        linked,
        linked_signed,
        require_authentication=True,
        minimum_generation=7,
        trusted_public_keys=trusted,
    )

    return {
        "implementation": implementation,
        "format_version": signed["version"],
        "scheme": validated["authentication"]["scheme"],
        "image_role": validated["image_role"],
        "key_id": signed["authentication"]["key_id"],
        "identity": signed["identity_sha256"],
        "signature_hex": signed["authentication"]["signature_hex"],
        "generation": validated["generation"],
        "rejected": rejected,
        "target_signed": {
            "identity": linked_signed["identity_sha256"],
            "generation": linked_signed["generation"],
            "valid": True,
        },
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))
