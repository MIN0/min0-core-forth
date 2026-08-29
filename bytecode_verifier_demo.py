"""Exercise instruction boundaries and capability derivation without execution."""

from __future__ import annotations

import json

from min0_core_forth_linker import build_manifest
from min0_core_forth_verify import BytecodeVerificationError, verify_image_bytecode
from min0_core_forth_vm import Op


BASES = {"code": 0x1000, "dictionary": 0x4000, "data": 0x8000}


def _components(code: bytes, dictionary: bytes = b"") -> dict[str, bytes]:
    return {"code": code, "dictionary": dictionary, "data": b""}


def _record(section: str, offset: int, target: str, kind: str) -> dict:
    return {
        "section": section,
        "offset": offset,
        "target": target,
        "width": 4,
        "kind": kind,
    }


def _rejected(operation) -> bool:
    try:
        operation()
    except BytecodeVerificationError:
        return True
    return False


def run_demo(implementation: str = "python") -> dict[str, object]:
    literal_25 = bytes([Op.LIT]) + (0x25).to_bytes(4, "little") + bytes([Op.EXIT])
    literal_summary = verify_image_bytecode(
        _components(literal_25), BASES, build_manifest([])
    )

    dset_code = bytes([Op.DSET]) + (0x4004).to_bytes(4, "little") + bytes([Op.EXIT])
    dset_record = _record("code", 1, "dictionary", "defer-store-slot")
    dset_summary = verify_image_bytecode(
        _components(dset_code), BASES, build_manifest([dset_record])
    )

    missing_dset_record = _rejected(
        lambda: verify_image_bytecode(
            _components(dset_code), BASES, build_manifest([])
        )
    )
    fake_dset_record = _rejected(
        lambda: verify_image_bytecode(
            _components(literal_25), BASES, build_manifest([dset_record])
        )
    )
    truncated_operand = _rejected(
        lambda: verify_image_bytecode(
            _components(bytes([Op.CALL, 0, 0])), BASES, build_manifest([])
        )
    )
    invalid_opcode = _rejected(
        lambda: verify_image_bytecode(
            _components(bytes([0xFF])), BASES, build_manifest([])
        )
    )

    branch_code = (
        bytes([Op.LIT])
        + (123).to_bytes(4, "little")
        + bytes([Op.BRANCH])
        + (0x1002).to_bytes(4, "little")
        + bytes([Op.EXIT])
    )
    branch_record = _record("code", 6, "code", "branch")
    branch_into_operand = _rejected(
        lambda: verify_image_bytecode(
            _components(branch_code), BASES, build_manifest([branch_record])
        )
    )

    dictionary_pointer = (0x1002).to_bytes(4, "little")
    entry_record = _record("dictionary", 0, "code", "colon-code")
    entry_into_operand = _rejected(
        lambda: verify_image_bytecode(
            _components(literal_25, dictionary_pointer),
            BASES,
            build_manifest([entry_record]),
        )
    )
    return {
        "implementation": implementation,
        "literal_0x25_capabilities": literal_summary["capabilities"],
        "literal_instruction_count": literal_summary["instruction_count"],
        "dset_capabilities": dset_summary["capabilities"],
        "dset_addresses": dset_summary["dset_addresses"],
        "rejected": {
            "missing_dset_record": missing_dset_record,
            "fake_dset_record": fake_dset_record,
            "truncated_operand": truncated_operand,
            "invalid_opcode": invalid_opcode,
            "branch_into_operand": branch_into_operand,
            "entry_into_operand": entry_into_operand,
        },
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))
