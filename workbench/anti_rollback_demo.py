"""Exercise signed generation checks and commit-after-success policy."""

from __future__ import annotations

import json

from auth_comparison_demo import ED25519_TEST_SEED
from min0_core_forth_auth import (
    ed25519_private_from_seed,
    ed25519_public_bytes,
    ed25519_sign,
    ed25519_verify,
)
from min0_core_forth_generation import GenerationError, TrustedGeneration
from min0_core_forth_image import (
    MAX_GENERATION,
    ImageError,
    build_image_envelope,
    link_image_envelope,
    validate_image_envelope,
)
from image_envelope_demo import (
    SOURCE_BASES,
    SOURCE_LIMITS,
    TARGET_BASES,
    TARGET_LIMITS,
    build_source_image,
)


def _is_rejected(operation, errors: tuple[type[Exception], ...]) -> bool:
    try:
        operation()
    except errors:
        return True
    return False


def run_demo(implementation: str = "python") -> dict:
    images = {}
    private_key = ed25519_private_from_seed(ED25519_TEST_SEED)
    public_key = ed25519_public_bytes(private_key)
    for generation in (6, 7, 8):
        components, envelope = build_source_image(generation)
        signature = ed25519_sign(envelope["identity_sha256"], private_key)
        images[generation] = (components, envelope, signature)

    trusted = TrustedGeneration(7)
    old_components, old_envelope, old_signature = images[6]
    old_signature_valid = ed25519_verify(
        old_envelope["identity_sha256"], public_key, old_signature
    )
    old_rejected = _is_rejected(
        lambda: validate_image_envelope(
            old_components,
            old_envelope,
            minimum_generation=trusted.minimum_accepted,
        ),
        (ImageError,),
    )

    current_components, current_envelope, current_signature = images[7]
    current_signature_valid = ed25519_verify(
        current_envelope["identity_sha256"], public_key, current_signature
    )
    validate_image_envelope(
        current_components,
        current_envelope,
        minimum_generation=trusted.minimum_accepted,
    )

    next_components, next_envelope, next_signature = images[8]
    next_signature_valid = ed25519_verify(
        next_envelope["identity_sha256"], public_key, next_signature
    )
    validate_image_envelope(
        next_components,
        next_envelope,
        minimum_generation=trusted.minimum_accepted,
    )
    trusted.authorize(next_envelope["generation"])
    before_failed_install = trusted.minimum_accepted
    # An install failure deliberately has no commit call.
    after_failed_install = trusted.minimum_accepted
    after_successful_install = trusted.commit(next_envelope["generation"])
    current_rejected_after_commit = _is_rejected(
        lambda: validate_image_envelope(
            current_components,
            current_envelope,
            minimum_generation=trusted.minimum_accepted,
        ),
        (ImageError,),
    )

    _linked, linked_envelope = link_image_envelope(
        next_components,
        next_envelope,
        TARGET_BASES,
        TARGET_LIMITS,
        minimum_generation=7,
    )

    components, template = build_source_image(0)
    negative_rejected = _is_rejected(
        lambda: build_image_envelope(
            components,
            SOURCE_BASES,
            SOURCE_LIMITS,
            template["allocator"],
            template["manifest"],
            generation=-1,
        ),
        (ImageError,),
    )
    overflow_rejected = _is_rejected(
        lambda: build_image_envelope(
            components,
            SOURCE_BASES,
            SOURCE_LIMITS,
            template["allocator"],
            template["manifest"],
            generation=MAX_GENERATION + 1,
        ),
        (ImageError,),
    )
    lower_commit_rejected = _is_rejected(
        lambda: trusted.commit(7), (GenerationError,)
    )

    return {
        "implementation": implementation,
        "format_version": next_envelope["version"],
        "identities": {
            str(generation): images[generation][1]["identity_sha256"]
            for generation in (6, 7, 8)
        },
        "signatures": {
            str(generation): images[generation][2].hex()
            for generation in (6, 7, 8)
        },
        "signature_valid": {
            "old": old_signature_valid,
            "current": current_signature_valid,
            "next": next_signature_valid,
        },
        "old_signed_image_rejected": old_rejected,
        "trusted_state": {
            "before_failed_install": before_failed_install,
            "after_failed_install": after_failed_install,
            "after_successful_install": after_successful_install,
        },
        "current_rejected_after_commit": current_rejected_after_commit,
        "linked_generation": linked_envelope["generation"],
        "bounds": {
            "negative_rejected": negative_rejected,
            "overflow_rejected": overflow_rejected,
            "lower_commit_rejected": lower_commit_rejected,
        },
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))
