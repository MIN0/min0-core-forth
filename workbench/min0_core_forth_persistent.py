"""Bounded binary container and canonical metadata parser for MIN0 CORE FORTH."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


PERSISTENT_MAGIC = b"FCPKG0\r\n"
PERSISTENT_VERSION = 1
HEADER = struct.Struct("<8sHHHHIIII")
DIRECTORY_ENTRY = struct.Struct("<16sIIII")
TRAILER_SIZE = 32
KIND_CODES = {"image": 1, "trust-bundle": 2, "root-policy-chain": 3}
CODE_KINDS = {value: key for key, value in KIND_CODES.items()}
KIND_SECTIONS = {
    "image": ("envelope", "code", "dictionary", "data"),
    "trust-bundle": ("trust-bundle",),
    "root-policy-chain": ("root-chain",),
}
SECTION_NAME_PATTERN = re.compile(r"[a-z][a-z0-9-]{0,14}")
MAX_JSON_DEPTH = 32
MAX_JSON_STRING = 4096
MAX_JSON_NUMBER_DIGITS = 20
MAX_JSON_NODES = 20_000


class PersistentFormatError(ValueError):
    pass


@dataclass(frozen=True)
class ParserLimits:
    max_file_bytes: int = 1_048_576
    max_sections: int = 8
    max_payload_bytes: int = 786_432
    max_section_bytes: int = 524_288
    max_metadata_bytes: int = 262_144

    def __post_init__(self) -> None:
        values = (
            self.max_file_bytes,
            self.max_sections,
            self.max_payload_bytes,
            self.max_section_bytes,
            self.max_metadata_bytes,
        )
        if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in values):
            raise PersistentFormatError("parser limits must be positive integers")
        if self.max_sections > 0xFFFF:
            raise PersistentFormatError("max_sections exceeds container field")
        if self.max_payload_bytes > self.max_file_bytes:
            raise PersistentFormatError("payload limit exceeds file limit")
        if self.max_metadata_bytes > self.max_section_bytes:
            raise PersistentFormatError("metadata limit exceeds section limit")


DEFAULT_LIMITS = ParserLimits()


class _DuplicateKeyError(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(f"duplicate JSON key {key}")
        result[key] = value
    return result


def _normalize_json(value: object, *, depth: int = 0, counter: list[int] | None = None) -> object:
    if counter is None:
        counter = [0]
    counter[0] += 1
    if counter[0] > MAX_JSON_NODES:
        raise PersistentFormatError("metadata contains too many JSON values")
    if depth > MAX_JSON_DEPTH:
        raise PersistentFormatError("metadata nesting is too deep")
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        if len(str(abs(value))) > MAX_JSON_NUMBER_DIGITS:
            raise PersistentFormatError("metadata integer is too long")
        return value
    if isinstance(value, float):
        raise PersistentFormatError("floating-point metadata is forbidden")
    if isinstance(value, str):
        if len(value) > MAX_JSON_STRING:
            raise PersistentFormatError("metadata string is too long")
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        for raw_key, item in value.items():
            if not isinstance(raw_key, str):
                raise PersistentFormatError("metadata object keys must be strings")
            if len(raw_key) > MAX_JSON_STRING:
                raise PersistentFormatError("metadata object key is too long")
            if raw_key in normalized:
                raise PersistentFormatError("metadata contains duplicate normalized keys")
            normalized[raw_key] = _normalize_json(
                item, depth=depth + 1, counter=counter
            )
        return {key: normalized[key] for key in sorted(normalized)}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray, memoryview)):
        return [
            _normalize_json(item, depth=depth + 1, counter=counter)
            for item in value
        ]
    raise PersistentFormatError("metadata contains an unsupported JSON value")


def canonical_json_bytes(value: object) -> bytes:
    normalized = _normalize_json(value)
    try:
        return json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise PersistentFormatError("metadata cannot be encoded canonically") from exc


def _preflight_json(text: str) -> None:
    depth = 0
    in_string = False
    escaped = False
    string_length = 0
    index = 0
    while index < len(text):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            else:
                string_length += 1
                if string_length > MAX_JSON_STRING:
                    raise PersistentFormatError("metadata string is too long")
            index += 1
            continue
        if char == '"':
            in_string = True
            string_length = 0
        elif char in "[{":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                raise PersistentFormatError("metadata nesting is too deep")
        elif char in "]}":
            depth -= 1
            if depth < 0:
                raise PersistentFormatError("metadata nesting is malformed")
        elif char == "-" or char.isdigit():
            start = index + (1 if char == "-" else 0)
            cursor = start
            while cursor < len(text) and text[cursor].isdigit():
                cursor += 1
            if cursor - start > MAX_JSON_NUMBER_DIGITS:
                raise PersistentFormatError("metadata number is too long")
            index = cursor - 1
        index += 1
    if in_string or escaped or depth != 0:
        raise PersistentFormatError("metadata JSON is incomplete")


def decode_canonical_json(raw: object, *, limits: ParserLimits = DEFAULT_LIMITS) -> object:
    if not isinstance(raw, (bytes, bytearray, memoryview)):
        raise PersistentFormatError("metadata section must be bytes")
    encoded = bytes(raw)
    if len(encoded) > limits.max_metadata_bytes:
        raise PersistentFormatError("metadata section exceeds configured limit")
    try:
        text = encoded.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise PersistentFormatError("metadata is not valid UTF-8") from exc
    if "\x00" in text:
        raise PersistentFormatError("metadata contains NUL")
    _preflight_json(text)

    def parse_int(token: str) -> int:
        if len(token.lstrip("-")) > MAX_JSON_NUMBER_DIGITS:
            raise PersistentFormatError("metadata integer is too long")
        return int(token)

    def reject_float(_token: str) -> float:
        raise PersistentFormatError("floating-point metadata is forbidden")

    def reject_constant(_token: str) -> object:
        raise PersistentFormatError("non-finite metadata number is forbidden")

    try:
        value = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_int=parse_int,
            parse_float=reject_float,
            parse_constant=reject_constant,
        )
    except PersistentFormatError:
        raise
    except (_DuplicateKeyError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise PersistentFormatError("metadata JSON is malformed") from exc
    normalized = _normalize_json(value)
    if canonical_json_bytes(normalized) != encoded:
        raise PersistentFormatError("metadata JSON is not canonical")
    return normalized


def _section_name_bytes(name: str) -> bytes:
    if not isinstance(name, str) or SECTION_NAME_PATTERN.fullmatch(name) is None:
        raise PersistentFormatError("section name is malformed")
    encoded = name.encode("ascii")
    return encoded + b"\0" * (16 - len(encoded))


def _decode_section_name(raw: bytes) -> str:
    prefix = raw.split(b"\0", 1)[0]
    try:
        name = prefix.decode("ascii")
    except UnicodeDecodeError as exc:
        raise PersistentFormatError("section name is not ASCII") from exc
    if _section_name_bytes(name) != raw:
        raise PersistentFormatError("section name padding is malformed")
    return name


def encode_package(
    kind: str,
    sections: Mapping[str, object],
    *,
    limits: ParserLimits = DEFAULT_LIMITS,
) -> bytes:
    if kind not in KIND_CODES:
        raise PersistentFormatError("persistent package kind is unsupported")
    expected_names = KIND_SECTIONS[kind]
    if not isinstance(sections, Mapping) or set(sections) != set(expected_names):
        raise PersistentFormatError("persistent package sections do not match kind")
    if len(expected_names) > limits.max_sections:
        raise PersistentFormatError("section count exceeds configured limit")
    normalized: dict[str, bytes] = {}
    for name in expected_names:
        value = sections[name]
        if not isinstance(value, (bytes, bytearray, memoryview)):
            raise PersistentFormatError(f"section {name} must be bytes")
        encoded = bytes(value)
        section_limit = (
            limits.max_metadata_bytes
            if name in ("envelope", "trust-bundle", "root-chain")
            else limits.max_section_bytes
        )
        if len(encoded) > section_limit:
            raise PersistentFormatError(f"section {name} exceeds configured limit")
        normalized[name] = encoded
    payload_bytes = sum(len(normalized[name]) for name in expected_names)
    if payload_bytes > limits.max_payload_bytes:
        raise PersistentFormatError("package payload exceeds configured limit")
    directory_bytes = len(expected_names) * DIRECTORY_ENTRY.size
    file_bytes = HEADER.size + directory_bytes + payload_bytes + TRAILER_SIZE
    if file_bytes > limits.max_file_bytes:
        raise PersistentFormatError("package exceeds configured file limit")
    header = HEADER.pack(
        PERSISTENT_MAGIC,
        PERSISTENT_VERSION,
        KIND_CODES[kind],
        len(expected_names),
        0,
        directory_bytes,
        payload_bytes,
        file_bytes,
        0,
    )
    directory = bytearray()
    offset = 0
    for name in expected_names:
        data = normalized[name]
        directory.extend(
            DIRECTORY_ENTRY.pack(_section_name_bytes(name), offset, len(data), 0, 0)
        )
        offset += len(data)
    payload = b"".join(normalized[name] for name in expected_names)
    body = header + bytes(directory) + payload
    return body + hashlib.sha256(body).digest()


def decode_package(
    raw: object, *, limits: ParserLimits = DEFAULT_LIMITS
) -> dict[str, object]:
    if not isinstance(raw, (bytes, bytearray, memoryview)):
        raise PersistentFormatError("persistent package must be bytes")
    encoded = bytes(raw)
    if len(encoded) > limits.max_file_bytes:
        raise PersistentFormatError("package exceeds configured file limit")
    if len(encoded) < HEADER.size + TRAILER_SIZE:
        raise PersistentFormatError("package is shorter than fixed framing")
    try:
        (
            magic,
            version,
            kind_code,
            section_count,
            flags,
            directory_bytes,
            payload_bytes,
            file_bytes,
            reserved,
        ) = HEADER.unpack_from(encoded)
    except struct.error as exc:
        raise PersistentFormatError("package header is incomplete") from exc
    if magic != PERSISTENT_MAGIC:
        raise PersistentFormatError("package magic is unsupported")
    if version != PERSISTENT_VERSION:
        raise PersistentFormatError("package version is unsupported")
    if kind_code not in CODE_KINDS:
        raise PersistentFormatError("package kind is unsupported")
    kind = CODE_KINDS[kind_code]
    expected_names = KIND_SECTIONS[kind]
    if section_count == 0 or section_count > limits.max_sections:
        raise PersistentFormatError("package section count is invalid")
    if section_count != len(expected_names):
        raise PersistentFormatError("package section count disagrees with kind")
    if flags != 0 or reserved != 0:
        raise PersistentFormatError("package header contains unsupported flags")
    expected_directory_bytes = section_count * DIRECTORY_ENTRY.size
    if directory_bytes != expected_directory_bytes:
        raise PersistentFormatError("package directory length is invalid")
    if payload_bytes > limits.max_payload_bytes:
        raise PersistentFormatError("package payload exceeds configured limit")
    expected_file_bytes = HEADER.size + directory_bytes + payload_bytes + TRAILER_SIZE
    if file_bytes != expected_file_bytes or file_bytes != len(encoded):
        raise PersistentFormatError("package file length is inconsistent")
    payload_start = HEADER.size + directory_bytes
    payload_end = payload_start + payload_bytes
    body = encoded[:payload_end]
    if not hmac.compare_digest(hashlib.sha256(body).digest(), encoded[payload_end:]):
        raise PersistentFormatError("package checksum mismatch")
    sections: dict[str, bytes] = {}
    expected_offset = 0
    for index, expected_name in enumerate(expected_names):
        directory_offset = HEADER.size + index * DIRECTORY_ENTRY.size
        try:
            raw_name, offset, length, entry_flags, entry_reserved = DIRECTORY_ENTRY.unpack_from(
                encoded, directory_offset
            )
        except struct.error as exc:
            raise PersistentFormatError("package directory entry is incomplete") from exc
        name = _decode_section_name(raw_name)
        if name != expected_name:
            raise PersistentFormatError("package sections are duplicate, missing, or reordered")
        if entry_flags != 0 or entry_reserved != 0:
            raise PersistentFormatError("section contains unsupported flags")
        if offset != expected_offset:
            raise PersistentFormatError("section ranges overlap or contain a gap")
        section_limit = (
            limits.max_metadata_bytes
            if name in ("envelope", "trust-bundle", "root-chain")
            else limits.max_section_bytes
        )
        if length > section_limit or offset + length > payload_bytes:
            raise PersistentFormatError(f"section {name} length is invalid")
        start = payload_start + offset
        sections[name] = encoded[start : start + length]
        expected_offset += length
    if expected_offset != payload_bytes:
        raise PersistentFormatError("package payload contains unclaimed bytes")
    return {"kind": kind, "sections": sections, "sha256": hashlib.sha256(body).hexdigest()}


def read_package_file(
    path: str | Path, *, limits: ParserLimits = DEFAULT_LIMITS
) -> dict[str, object]:
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(limits.max_file_bytes + 1)
    except OSError as exc:
        raise PersistentFormatError(f"cannot read persistent package: {exc}") from exc
    if len(raw) > limits.max_file_bytes:
        raise PersistentFormatError("package exceeds configured file limit")
    return decode_package(raw, limits=limits)


def write_package_file(
    path: str | Path,
    kind: str,
    sections: Mapping[str, object],
    *,
    limits: ParserLimits = DEFAULT_LIMITS,
) -> dict[str, object]:
    raw = encode_package(kind, sections, limits=limits)
    try:
        Path(path).write_bytes(raw)
    except OSError as exc:
        raise PersistentFormatError(f"cannot write persistent package: {exc}") from exc
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def encode_image_package(
    components: Mapping[str, object],
    envelope: object,
    *,
    limits: ParserLimits = DEFAULT_LIMITS,
) -> bytes:
    return encode_package(
        "image",
        {
            "envelope": canonical_json_bytes(envelope),
            "code": components.get("code"),
            "dictionary": components.get("dictionary"),
            "data": components.get("data"),
        },
        limits=limits,
    )


def decode_image_package(
    raw: object, *, limits: ParserLimits = DEFAULT_LIMITS
) -> tuple[dict[str, bytes], dict]:
    package = decode_package(raw, limits=limits)
    return _decode_image_sections(package, limits=limits)


def _decode_image_sections(
    package: Mapping[str, object], *, limits: ParserLimits = DEFAULT_LIMITS
) -> tuple[dict[str, bytes], dict]:
    if package["kind"] != "image":
        raise PersistentFormatError("persistent package is not an image")
    sections = package["sections"]
    envelope = decode_canonical_json(sections["envelope"], limits=limits)
    if not isinstance(envelope, dict):
        raise PersistentFormatError("image envelope metadata must be an object")
    return (
        {name: sections[name] for name in ("code", "dictionary", "data")},
        envelope,
    )


def write_image_file(
    path: str | Path,
    components: Mapping[str, object],
    envelope: object,
    *,
    limits: ParserLimits = DEFAULT_LIMITS,
) -> dict[str, object]:
    return write_package_file(
        path,
        "image",
        {
            "envelope": canonical_json_bytes(envelope),
            "code": components.get("code"),
            "dictionary": components.get("dictionary"),
            "data": components.get("data"),
        },
        limits=limits,
    )


def read_image_file(
    path: str | Path, *, limits: ParserLimits = DEFAULT_LIMITS
) -> tuple[dict[str, bytes], dict]:
    return _decode_image_sections(read_package_file(path, limits=limits), limits=limits)


def encode_trust_bundle_package(
    bundle: object, *, limits: ParserLimits = DEFAULT_LIMITS
) -> bytes:
    return encode_package(
        "trust-bundle",
        {"trust-bundle": canonical_json_bytes(bundle)},
        limits=limits,
    )


def decode_trust_bundle_package(
    raw: object, *, limits: ParserLimits = DEFAULT_LIMITS
) -> dict:
    package = decode_package(raw, limits=limits)
    if package["kind"] != "trust-bundle":
        raise PersistentFormatError("persistent package is not a trust bundle")
    value = decode_canonical_json(
        package["sections"]["trust-bundle"], limits=limits
    )
    if not isinstance(value, dict):
        raise PersistentFormatError("trust bundle metadata must be an object")
    return value


def encode_root_policy_chain_package(
    chain: object, *, limits: ParserLimits = DEFAULT_LIMITS
) -> bytes:
    return encode_package(
        "root-policy-chain",
        {"root-chain": canonical_json_bytes(chain)},
        limits=limits,
    )


def decode_root_policy_chain_package(
    raw: object, *, limits: ParserLimits = DEFAULT_LIMITS
) -> list:
    package = decode_package(raw, limits=limits)
    if package["kind"] != "root-policy-chain":
        raise PersistentFormatError("persistent package is not a root policy chain")
    value = decode_canonical_json(package["sections"]["root-chain"], limits=limits)
    if not isinstance(value, list):
        raise PersistentFormatError("root policy chain metadata must be an array")
    return value
