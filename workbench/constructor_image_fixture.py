"""Write or read the cross-language constructor-plan audit envelope."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from min0_core_forth_dictionary import CONSTRUCTOR_PLAN_VERSION, RuntimeDictionary
from min0_core_forth_outer import DEFAULT_CODE_BASE, OuterInterpreter, install_core_primitives
from min0_core_forth_vm import Min0CoreForthVM, MemoryRegion, RegionMemory


IMAGE_FORMAT = "min0-core-forth-constructor-audit"
IMAGE_VERSION = 1


def make_system():
    bus = RegionMemory(
        0x10000,
        [
            MemoryRegion("CODE", 0, 0x4000, "rwx", programmable=True),
            MemoryRegion("DICTIONARY", 0x4000, 0x4000, "rw"),
            MemoryRegion("DATA", 0x8000, 0x8000, "rw"),
        ],
    )
    vm = Min0CoreForthVM(memory_bus=bus)
    dictionary = RuntimeDictionary(
        vm, base=0x4000, limit=0x8000, body_base=0x8000, body_limit=0x10000
    )
    return vm, dictionary


def build_envelope(writer: str = "python") -> dict:
    vm, dictionary = make_system()
    install_core_primitives(dictionary)
    outer = OuterInterpreter(vm, dictionary)
    outer.interpret(": RECORD: CREATE C, ALLOT ALIGN ;")
    record = dictionary.find("RECORD:")
    assert record is not None
    plan, _behavior = dictionary.read_definer_descriptor(record)
    return {
        "format": IMAGE_FORMAT,
        "version": IMAGE_VERSION,
        "writer": writer,
        "memory_size": 0x10000,
        "code_base": DEFAULT_CODE_BASE,
        "code_here": outer.code_here,
        "dictionary_base": dictionary.base,
        "dictionary_limit": dictionary.limit,
        "header_here": dictionary.here,
        "latest": dictionary.latest,
        "body_base": dictionary.body_base,
        "body_limit": dictionary.body_limit,
        "data_here": dictionary.data_here,
        "record_plan": plan,
        "code_hex": vm.read_bytes(DEFAULT_CODE_BASE, outer.code_here - DEFAULT_CODE_BASE).hex(),
        "dictionary_hex": dictionary.image().hex(),
        "body_hex": dictionary.body_image().hex(),
    }


def _require_integer(envelope: dict, name: str, expected: int | None = None) -> int:
    value = envelope.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"constructor image field {name} must be an integer")
    if expected is not None and value != expected:
        raise ValueError(f"constructor image field {name} is unsupported")
    return value


def load_envelope(envelope: dict, reader: str = "python") -> dict:
    if envelope.get("format") != IMAGE_FORMAT:
        raise ValueError("unsupported constructor image format")
    _require_integer(envelope, "version", IMAGE_VERSION)
    _require_integer(envelope, "memory_size", 0x10000)
    code_base = _require_integer(envelope, "code_base", DEFAULT_CODE_BASE)
    code_here = _require_integer(envelope, "code_here")
    dictionary_base = _require_integer(envelope, "dictionary_base", 0x4000)
    dictionary_limit = _require_integer(envelope, "dictionary_limit", 0x8000)
    header_here = _require_integer(envelope, "header_here")
    latest = _require_integer(envelope, "latest")
    body_base = _require_integer(envelope, "body_base", 0x8000)
    body_limit = _require_integer(envelope, "body_limit", 0x10000)
    data_here = _require_integer(envelope, "data_here")
    record_plan = _require_integer(envelope, "record_plan")
    def decode_hex(name: str) -> bytes:
        value = envelope.get(name)
        if not isinstance(value, str) or len(value) % 2 or not re.fullmatch(r"[0-9a-f]*", value):
            raise ValueError("constructor image contains invalid hex data")
        return bytes.fromhex(value)

    code = decode_hex("code_hex")
    headers = decode_hex("dictionary_hex")
    body = decode_hex("body_hex")
    if code_here - code_base != len(code):
        raise ValueError("constructor image CODE length disagrees with code HERE")
    if header_here - dictionary_base != len(headers):
        raise ValueError("constructor image DICTIONARY length disagrees with header HERE")
    if data_here - body_base != len(body):
        raise ValueError("constructor image DATA length disagrees with data HERE")

    vm, dictionary = make_system()
    vm.load(code, code_base)
    dictionary.load_images(headers, latest=latest, body_image=body)
    if dictionary.here != header_here or dictionary.data_here != data_here:
        raise ValueError("constructor image allocator state did not restore")
    outer = OuterInterpreter(vm, dictionary, code_base=code_here)
    record = dictionary.find("RECORD:")
    if record is None:
        raise ValueError("constructor image has no RECORD: definer")
    plan, behavior = dictionary.read_definer_descriptor(record)
    if plan != record_plan or behavior != 0:
        raise ValueError("constructor image RECORD: metadata disagrees")
    actions = [action for _code, action in dictionary.read_constructor_plan(record)]
    stack = outer.interpret("2 0x1AB RECORD: ITEM ITEM")
    item = dictionary.find("ITEM")
    assert item is not None
    return {
        "reader": reader,
        "source_writer": envelope.get("writer"),
        "plan_version": vm.read_cell(plan + 4),
        "actions": actions,
        "stack": stack,
        "item_body": item.payload,
        "body_hex": vm.read_bytes(item.payload, 4).hex(),
        "data_here": dictionary.data_here,
    }


def write_envelope(path: Path) -> dict:
    envelope = build_envelope()
    raw = json.dumps(envelope, sort_keys=True, separators=(",", ":")) + "\n"
    encoded = raw.encode("utf-8")
    path.write_bytes(encoded)
    return {
        "writer": "python",
        "bytes": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("write", "read"))
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    if args.mode == "write":
        result = write_envelope(args.image)
    else:
        envelope = json.loads(args.image.read_text(encoding="utf-8"))
        result = load_envelope(envelope)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
