"""Linear bytecode verifier and capability derivation for Reference32 images."""

from __future__ import annotations

from collections.abc import Mapping

from min0_core_forth_linker import SECTIONS
from min0_core_forth_vm import Op


OPERAND_OPS = frozenset(
    {
        Op.LIT,
        Op.CALL,
        Op.ICALL,
        Op.DSET,
        Op.BRANCH,
        Op.ZBRANCH,
        Op.LOOP,
        Op.PLOOP,
        Op.QDO,
        Op.LEAVE,
        Op.SERVICE,
    }
)

REQUIRED_CODE_RELOCATIONS = {
    Op.CALL: ("code", frozenset({"call", "does-call"})),
    Op.ICALL: ("dictionary", frozenset({"defer-slot"})),
    Op.DSET: ("dictionary", frozenset({"defer-store-slot"})),
    Op.BRANCH: ("code", frozenset({"branch"})),
    Op.ZBRANCH: ("code", frozenset({"zbranch"})),
    Op.LOOP: ("code", frozenset({"loop"})),
    Op.PLOOP: ("code", frozenset({"ploop"})),
    Op.QDO: ("code", frozenset({"qdo"})),
    Op.LEAVE: ("code", frozenset({"leave"})),
}

OPTIONAL_LITERAL_RELOCATIONS = frozenset(
    {
        ("dictionary", "xt-literal"),
        ("dictionary", "action-of-slot"),
        ("data", "data-literal"),
        ("data", "does-body"),
        ("data", "string-address"),
    }
)


class BytecodeVerificationError(ValueError):
    pass


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise BytecodeVerificationError(f"{label} must be an integer")
    return value


def _normalize_components(components: Mapping[str, object]) -> dict[str, bytes]:
    if not isinstance(components, Mapping):
        raise BytecodeVerificationError("components must be a mapping")
    result: dict[str, bytes] = {}
    for section in SECTIONS:
        value = components.get(section)
        if not isinstance(value, (bytes, bytearray, memoryview)):
            raise BytecodeVerificationError(f"component {section} must be bytes")
        result[section] = bytes(value)
    return result


def _normalize_bases(bases: Mapping[str, object]) -> dict[str, int]:
    if not isinstance(bases, Mapping):
        raise BytecodeVerificationError("component bases must be a mapping")
    return {
        section: _integer(bases.get(section), f"base {section}")
        for section in SECTIONS
    }


def verify_image_bytecode(
    components: Mapping[str, object],
    bases: Mapping[str, object],
    manifest: object,
) -> dict[str, object]:
    """Decode all CODE bytes and cross-check every typed CODE reference."""

    images = _normalize_components(components)
    normalized_bases = _normalize_bases(bases)
    if not isinstance(manifest, Mapping):
        raise BytecodeVerificationError("manifest must be a mapping")
    records = manifest.get("records")
    if not isinstance(records, list):
        raise BytecodeVerificationError("manifest records must be a list")

    code_records: dict[int, Mapping[str, object]] = {}
    all_records: list[Mapping[str, object]] = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise BytecodeVerificationError(
                f"relocation record {index} must be a mapping"
            )
        all_records.append(record)
        if record.get("section") != "code":
            continue
        offset = _integer(record.get("offset"), f"relocation record {index} offset")
        if offset in code_records:
            raise BytecodeVerificationError(
                f"multiple CODE relocations at offset {offset}"
            )
        code_records[offset] = record

    code = images["code"]
    code_base = normalized_bases["code"]
    boundaries: set[int] = set()
    instructions: list[tuple[int, Op, int | None]] = []
    consumed_code_records: set[int] = set()
    service_ids: set[int] = set()
    service_addresses: list[int] = []
    offset = 0
    while offset < len(code):
        boundaries.add(code_base + offset)
        raw_opcode = code[offset]
        try:
            op = Op(raw_opcode)
        except ValueError as exc:
            raise BytecodeVerificationError(
                f"invalid opcode 0x{raw_opcode:02X} at CODE+0x{offset:X}"
            ) from exc
        instruction_offset = offset
        offset += 1
        operand = None
        if op in OPERAND_OPS:
            if offset + 4 > len(code):
                raise BytecodeVerificationError(
                    f"truncated operand for {op.name} at CODE+0x{instruction_offset:X}"
                )
            operand = int.from_bytes(code[offset : offset + 4], "little")
            record = code_records.get(offset)
            if op is Op.LIT:
                if record is not None:
                    pair = (record.get("target"), record.get("kind"))
                    if pair not in OPTIONAL_LITERAL_RELOCATIONS:
                        raise BytecodeVerificationError(
                            f"LIT at CODE+0x{instruction_offset:X} has incompatible relocation"
                        )
                    consumed_code_records.add(offset)
            elif op is Op.SERVICE:
                if record is not None:
                    raise BytecodeVerificationError(
                        f"SERVICE at CODE+0x{instruction_offset:X} must not have relocation"
                    )
                if operand == 0:
                    raise BytecodeVerificationError(
                        f"SERVICE at CODE+0x{instruction_offset:X} uses reserved id zero"
                    )
                service_ids.add(operand)
                service_addresses.append(code_base + instruction_offset)
            else:
                expected_target, expected_kinds = REQUIRED_CODE_RELOCATIONS[op]
                if record is None:
                    raise BytecodeVerificationError(
                        f"{op.name} at CODE+0x{instruction_offset:X} lacks typed relocation"
                    )
                if (
                    record.get("target") != expected_target
                    or record.get("kind") not in expected_kinds
                    or record.get("width") != 4
                ):
                    raise BytecodeVerificationError(
                        f"{op.name} at CODE+0x{instruction_offset:X} has incompatible relocation"
                    )
                consumed_code_records.add(offset)
            offset += 4
        instructions.append((instruction_offset, op, operand))

    unexpected_records = sorted(set(code_records) - consumed_code_records)
    if unexpected_records:
        raise BytecodeVerificationError(
            f"CODE relocation at offset {unexpected_records[0]} is not an instruction operand"
        )

    code_end = code_base + len(code)
    direct_code_ops = {
        Op.CALL,
        Op.BRANCH,
        Op.ZBRANCH,
        Op.LOOP,
        Op.PLOOP,
        Op.QDO,
        Op.LEAVE,
    }
    for instruction_offset, op, operand in instructions:
        if op in direct_code_ops and operand not in boundaries:
            rendered = 0 if operand is None else operand
            raise BytecodeVerificationError(
                f"{op.name} at CODE+0x{instruction_offset:X} targets "
                f"non-boundary 0x{rendered:08X}"
            )

    for index, record in enumerate(all_records):
        if record.get("target") != "code":
            continue
        section = record.get("section")
        if section not in SECTIONS:
            continue
        patch_offset = _integer(record.get("offset"), f"relocation record {index} offset")
        image = images[section]
        if patch_offset < 0 or patch_offset + 4 > len(image):
            continue
        target = int.from_bytes(image[patch_offset : patch_offset + 4], "little")
        if target not in boundaries:
            raise BytecodeVerificationError(
                f"relocation record {index} targets non-boundary 0x{target:08X}"
            )

    dset_offsets = [
        code_base + instruction_offset
        for instruction_offset, op, _operand in instructions
        if op is Op.DSET
    ]
    capabilities = ["compiled-defer-store"] if dset_offsets else []
    return {
        "instruction_count": len(instructions),
        "code_start": code_base,
        "code_end": code_end,
        "boundary_count": len(boundaries),
        "boundaries": sorted(boundaries),
        "capabilities": capabilities,
        "dset_addresses": dset_offsets,
        "service_ids": sorted(service_ids),
        "service_addresses": service_addresses,
    }
