"""Host-side authentication experiment for MIN0 CORE FORTH image identities."""

from __future__ import annotations

import hashlib
import hmac

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


AUTH_DOMAIN = b"MIN0-CORE-FORTH-IMAGE-AUTH-R0\0"
HMAC_SCHEME = "hmac-sha256"
ED25519_SCHEME = "ed25519"


class AuthenticationError(ValueError):
    pass


def authentication_message(identity_sha256: str) -> bytes:
    if (
        not isinstance(identity_sha256, str)
        or len(identity_sha256) != 64
        or identity_sha256.lower() != identity_sha256
    ):
        raise AuthenticationError("identity must be a lowercase SHA-256 hex string")
    try:
        digest = bytes.fromhex(identity_sha256)
    except ValueError as exc:
        raise AuthenticationError("identity contains non-hexadecimal data") from exc
    return AUTH_DOMAIN + digest


def hmac_sign(identity_sha256: str, secret_key: bytes) -> bytes:
    if not isinstance(secret_key, bytes) or len(secret_key) < 32:
        raise AuthenticationError("HMAC-SHA256 key must be at least 32 bytes")
    return hmac.new(secret_key, authentication_message(identity_sha256), hashlib.sha256).digest()


def hmac_verify(identity_sha256: str, secret_key: bytes, tag: bytes) -> bool:
    if not isinstance(tag, bytes) or len(tag) != 32:
        return False
    try:
        expected = hmac_sign(identity_sha256, secret_key)
    except AuthenticationError:
        return False
    return hmac.compare_digest(expected, tag)


def ed25519_private_from_seed(seed: bytes) -> Ed25519PrivateKey:
    if not isinstance(seed, bytes) or len(seed) != 32:
        raise AuthenticationError("Ed25519 seed must be 32 bytes")
    return Ed25519PrivateKey.from_private_bytes(seed)


def ed25519_public_bytes(private_key: Ed25519PrivateKey) -> bytes:
    return private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )


def ed25519_sign(identity_sha256: str, private_key: Ed25519PrivateKey) -> bytes:
    return private_key.sign(authentication_message(identity_sha256))


def ed25519_verify(identity_sha256: str, public_key: bytes, signature: bytes) -> bool:
    if not isinstance(public_key, bytes) or len(public_key) != 32:
        return False
    if not isinstance(signature, bytes) or len(signature) != 64:
        return False
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature, authentication_message(identity_sha256)
        )
    except (InvalidSignature, ValueError, AuthenticationError):
        return False
    return True
