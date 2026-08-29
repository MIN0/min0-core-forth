"""Compare HMAC-SHA256 and Ed25519 for one real MIN0 CORE FORTH image identity."""

from __future__ import annotations

import hashlib
import json
import time

from min0_core_forth_auth import (
    authentication_message,
    ed25519_private_from_seed,
    ed25519_public_bytes,
    ed25519_sign,
    ed25519_verify,
    hmac_sign,
    hmac_verify,
)
from image_envelope_demo import build_source_image


# Public, deterministic test fixtures only. Never use these keys in deployment.
HMAC_TEST_KEY = bytes(range(32))
ED25519_TEST_SEED = bytes(range(32, 64))
WRONG_HMAC_TEST_KEY = bytes(reversed(range(32)))
WRONG_ED25519_TEST_SEED = bytes([0xA5] * 32)


def _tamper_identity(identity: str) -> str:
    return ("0" if identity[0] != "0" else "1") + identity[1:]


def _benchmark(identity: str, hmac_tag: bytes, public_key: bytes, signature: bytes) -> dict:
    hmac_iterations = 2000
    ed_iterations = 300
    start = time.perf_counter_ns()
    for _ in range(hmac_iterations):
        hmac_verify(identity, HMAC_TEST_KEY, hmac_tag)
    hmac_us = (time.perf_counter_ns() - start) / hmac_iterations / 1000

    private_key = ed25519_private_from_seed(ED25519_TEST_SEED)
    start = time.perf_counter_ns()
    for _ in range(ed_iterations):
        ed25519_sign(identity, private_key)
    ed_sign_us = (time.perf_counter_ns() - start) / ed_iterations / 1000

    start = time.perf_counter_ns()
    for _ in range(ed_iterations):
        ed25519_verify(identity, public_key, signature)
    ed_verify_us = (time.perf_counter_ns() - start) / ed_iterations / 1000
    return {
        "hmac_verify_us": round(hmac_us, 3),
        "ed25519_sign_us": round(ed_sign_us, 3),
        "ed25519_verify_us": round(ed_verify_us, 3),
        "note": "host measurement only; not a target estimate",
    }


def run_demo(implementation: str = "python") -> dict:
    _components, envelope = build_source_image()
    identity = envelope["identity_sha256"]
    tampered_identity = _tamper_identity(identity)

    hmac_tag = hmac_sign(identity, HMAC_TEST_KEY)
    hmac_forged_tag = hmac_sign(tampered_identity, HMAC_TEST_KEY)

    private_key = ed25519_private_from_seed(ED25519_TEST_SEED)
    public_key = ed25519_public_bytes(private_key)
    wrong_public_key = ed25519_public_bytes(
        ed25519_private_from_seed(WRONG_ED25519_TEST_SEED)
    )
    signature = ed25519_sign(identity, private_key)
    public_object_can_sign = hasattr(private_key.public_key(), "sign")

    hmac_block = {
        "scheme": "hmac-sha256",
        "key_id": "fixture-hmac-01",
        "tag_hex": hmac_tag.hex(),
    }
    ed25519_block = {
        "scheme": "ed25519",
        "key_id": hashlib.sha256(public_key).hexdigest()[:16],
        "public_key_hex": public_key.hex(),
        "signature_hex": signature.hex(),
    }
    return {
        "implementation": implementation,
        "identity": identity,
        "message_bytes": len(authentication_message(identity)),
        "hmac": hmac_block,
        "ed25519": ed25519_block,
        "sizes": {
            "hmac_device_secret": len(HMAC_TEST_KEY),
            "hmac_tag": len(hmac_tag),
            "ed25519_signer_seed": len(ED25519_TEST_SEED),
            "ed25519_device_public": len(public_key),
            "ed25519_signature": len(signature),
        },
        "verification": {
            "hmac_valid": hmac_verify(identity, HMAC_TEST_KEY, hmac_tag),
            "hmac_tampered": hmac_verify(
                tampered_identity, HMAC_TEST_KEY, hmac_tag
            ),
            "hmac_wrong_key": hmac_verify(identity, WRONG_HMAC_TEST_KEY, hmac_tag),
            "ed25519_valid": ed25519_verify(identity, public_key, signature),
            "ed25519_tampered": ed25519_verify(
                tampered_identity, public_key, signature
            ),
            "ed25519_wrong_key": ed25519_verify(
                identity, wrong_public_key, signature
            ),
        },
        "device_compromise": {
            "hmac_verifier_can_forge": hmac_verify(
                tampered_identity, HMAC_TEST_KEY, hmac_forged_tag
            ),
            "ed25519_verifier_can_forge": public_object_can_sign,
        },
        "timing": _benchmark(identity, hmac_tag, public_key, signature),
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))
