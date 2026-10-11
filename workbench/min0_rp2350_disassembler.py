"""Independent Thumb decoder and linked-main audit for the RP2350 backend.

This module deliberately does not import or call emitter/linker encoding helpers.
It decodes emitted bytes in the opposite direction and compares their meaning
with the auditable backend plan.
"""

from __future__ import annotations

from dataclasses import dataclass
import struct
from typing import Any


class DisassemblyError(ValueError):
    pass


class MachineAuditError(ValueError):
    pass


@dataclass(frozen=True)
class DecodedInstruction:
    offset: int
    size: int
    mnemonic: str
    operands: tuple[str | int, ...]
    raw: bytes


CONDITION_NAMES = {
    0x0: "BEQ",
    0x1: "BNE",
    0x2: "BGEU",
    0x3: "BLTU",
    0xA: "BGE",
    0xB: "BLT",
}


def decode_thumb_instruction(
    code: bytes, offset: int = 0, *, image_base: int = 0,
) -> DecodedInstruction:
    if offset < 0 or offset % 2 or offset + 2 > len(code):
        raise DisassemblyError("Thumb instruction offset is outside aligned code")
    halfword = struct.unpack_from("<H", code, offset)[0]
    address = image_base + offset

    if halfword in {0xE92D, 0xE8BD}:
        second = _second_halfword(code, offset)
        mnemonic = "STMDB" if halfword == 0xE92D else "LDMIA"
        operands = ("sp!",) + _register_list(second)
        return _decoded(code, offset, 4, mnemonic, operands)

    if halfword & 0xF800 == 0xF000:
        second = _second_halfword(code, offset)
        if (second & 0xD000) not in {0x9000, 0xD000}:
            raise DisassemblyError(f"unsupported Thumb-2 branch at 0x{address:08x}")
        mnemonic = "BL" if (second & 0xD000) == 0xD000 else "B.W"
        target = address + 4 + _decode_wide_branch_displacement(halfword, second)
        return _decoded(code, offset, 4, mnemonic, (target,))

    if halfword == 0xBF00:
        return _decoded(code, offset, 2, "NOP", ())
    if halfword in {0xDE00, 0xDE01}:
        return _decoded(code, offset, 2, "UDF", (halfword & 0xFF,))
    if halfword & 0xFF87 == 0x4700:
        source = (halfword >> 3) & 0xF
        return _decoded(code, offset, 2, "BX", (_register(source),))
    if halfword & 0xFF00 == 0x4600:
        destination = (halfword & 7) | ((halfword >> 4) & 8)
        source = (halfword >> 3) & 0xF
        return _decoded(
            code, offset, 2, "MOV", (_register(destination), _register(source))
        )
    if halfword & 0xFF00 == 0x4500:
        left = (halfword & 7) | ((halfword >> 4) & 8)
        right = (halfword >> 3) & 0xF
        return _decoded(code, offset, 2, "CMP", (_register(left), _register(right)))

    if halfword & 0xFE00 in {0xB400, 0xBC00}:
        pop = halfword & 0xFE00 == 0xBC00
        mask = halfword & 0xFF
        if halfword & 0x100:
            mask |= 1 << (15 if pop else 14)
        return _decoded(
            code, offset, 2, "POP" if pop else "PUSH", _register_list(mask)
        )
    if halfword & 0xFF80 in {0xB000, 0xB080}:
        mnemonic = "SUB_SP" if halfword & 0xFF80 == 0xB080 else "ADD_SP"
        return _decoded(code, offset, 2, mnemonic, ((halfword & 0x7F) * 4,))
    if halfword & 0xF800 == 0xA800:
        destination = (halfword >> 8) & 7
        return _decoded(
            code, offset, 2, "ADD_FROM_SP",
            (_register(destination), (halfword & 0xFF) * 4),
        )
    if halfword & 0xF000 == 0x9000:
        load = bool(halfword & 0x0800)
        register = (halfword >> 8) & 7
        return _decoded(
            code, offset, 2, "LDR_SP" if load else "STR_SP",
            (_register(register), (halfword & 0xFF) * 4),
        )

    data_processing = {
        0x4000: "AND", 0x4040: "XOR", 0x41C0: "ROR",
        0x4280: "CMP", 0x4300: "OR", 0x4340: "MUL", 0x43C0: "MVN",
    }
    operation = data_processing.get(halfword & 0xFFC0)
    if operation is not None:
        destination = halfword & 7
        source = (halfword >> 3) & 7
        return _decoded(
            code, offset, 2, operation,
            (_register(destination), _register(source)),
        )

    if halfword & 0xFE00 in {0x1800, 0x1A00}:
        mnemonic = "ADD" if halfword & 0xFE00 == 0x1800 else "SUB"
        destination = halfword & 7
        left = (halfword >> 3) & 7
        right = (halfword >> 6) & 7
        return _decoded(
            code, offset, 2, mnemonic,
            (_register(destination), _register(left), _register(right)),
        )

    shift_bases = {0x0000: "LSL", 0x0800: "LSR", 0x1000: "ASR"}
    shift = shift_bases.get(halfword & 0xF800)
    if shift is not None:
        count = (halfword >> 6) & 31
        source = (halfword >> 3) & 7
        destination = halfword & 7
        return _decoded(
            code, offset, 2, shift,
            (_register(destination), _register(source), count),
        )

    if halfword & 0xF800 == 0x2000:
        destination = (halfword >> 8) & 7
        return _decoded(
            code, offset, 2, "MOVS", (_register(destination), halfword & 0xFF)
        )
    if halfword & 0xF800 == 0x2800:
        register = (halfword >> 8) & 7
        return _decoded(code, offset, 2, "CMP_IMM", (_register(register), halfword & 0xFF))
    if halfword & 0xF800 == 0x4800:
        destination = (halfword >> 8) & 7
        target = ((address + 4) & ~3) + ((halfword & 0xFF) * 4)
        return _decoded(code, offset, 2, "LDR_LITERAL", (_register(destination), target))
    if halfword & 0xF000 == 0xD000:
        condition = (halfword >> 8) & 0xF
        try:
            mnemonic = CONDITION_NAMES[condition]
        except KeyError as error:
            raise DisassemblyError(
                f"unsupported Thumb condition 0x{condition:x} at 0x{address:08x}"
            ) from error
        displacement = _sign_extend((halfword & 0xFF) << 1, 9)
        return _decoded(code, offset, 2, mnemonic, (address + 4 + displacement,))
    if halfword & 0xF800 == 0xE000:
        displacement = _sign_extend((halfword & 0x7FF) << 1, 12)
        return _decoded(code, offset, 2, "B", (address + 4 + displacement,))

    raise DisassemblyError(
        f"unsupported Thumb halfword 0x{halfword:04x} at 0x{address:08x}"
    )


def audit_linked_main(
    plan: Any,
    fragment: Any,
    main_size: int,
    *,
    image_base: int = 0,
) -> tuple[DecodedInstruction, ...]:
    """Decode the linked main body and prove it matches the backend plan."""

    if main_size < 0 or main_size > len(fragment.code) or main_size % 2:
        raise MachineAuditError("invalid main fragment boundary")
    if any(item.offset < main_size for item in fragment.relocations):
        raise MachineAuditError("main fragment still contains unresolved relocations")

    cursor = 0
    decoded: list[DecodedInstruction] = []
    for planned in plan.instructions:
        opcode = planned.opcode
        operands = planned.operands
        if opcode == "LABEL":
            label = str(operands[0])
            if fragment.labels.get(label) != cursor:
                raise MachineAuditError(f"label {label} does not match machine offset")
            continue

        if opcode == "PROLOGUE_SAVE":
            cursor = _expect_one(
                fragment, cursor, main_size, image_base, decoded,
                "STMDB", ("sp!",) + tuple(operands),
            )
        elif opcode == "CONTEXT_BIND":
            cursor = _expect_sequence(
                fragment, cursor, main_size, image_base, decoded,
                (("MOV", tuple(operands)), ("NOP", ())),
            )
        elif opcode in {
            "FRAME_LOAD", "RESULT_STAGE", "CHECKED_LD32", "STAGE_ST32", "FRAME_COMMIT",
        }:
            instruction = _decode_at(fragment, cursor, main_size, image_base)
            expected_label = f"@helper-thunk-{cursor:08x}"
            expected_target = fragment.labels.get(expected_label)
            if instruction.mnemonic != "BL" or expected_target is None:
                raise MachineAuditError(f"{opcode} is not linked to its helper thunk")
            if instruction.operands != (image_base + expected_target,):
                raise MachineAuditError(f"{opcode} helper thunk target mismatch")
            decoded.append(instruction)
            cursor += instruction.size
        elif opcode == "MOV":
            cursor = _expect_one(
                fragment, cursor, main_size, image_base, decoded, "MOV", tuple(operands)
            )
        elif opcode == "MOV_IMM32":
            instruction = _decode_at(fragment, cursor, main_size, image_base)
            if instruction.mnemonic != "LDR_LITERAL" or instruction.operands[0] != operands[0]:
                raise MachineAuditError("literal load does not match backend plan")
            literal_address = int(instruction.operands[1])
            literal_offset, value = _literal_value(fragment, literal_address, image_base)
            if literal_offset < main_size:
                raise MachineAuditError("literal load target is inside the main body")
            if value != int(operands[1]) & 0xFFFF_FFFF:
                raise MachineAuditError("literal pool value does not match backend plan")
            decoded.append(instruction)
            cursor += instruction.size
            cursor = _expect_one(
                fragment, cursor, main_size, image_base, decoded, "NOP", ()
            )
        elif opcode in {"ADD", "SUB"}:
            destination, source = operands
            cursor = _expect_one(
                fragment, cursor, main_size, image_base, decoded,
                opcode, (destination, destination, source),
            )
        elif opcode in {"AND", "XOR", "OR", "MUL"}:
            cursor = _expect_one(
                fragment, cursor, main_size, image_base, decoded, opcode, tuple(operands)
            )
        elif opcode == "MVN":
            register = operands[0]
            cursor = _expect_one(
                fragment, cursor, main_size, image_base, decoded, "MVN", (register, register)
            )
        elif opcode in {"LSL", "LSR", "ASR"}:
            register, count = operands
            if int(count) == 0:
                expected = (("MOV", (register, register)),)
            else:
                expected = ((opcode, (register, register, int(count))),)
            cursor = _expect_sequence(
                fragment, cursor, main_size, image_base, decoded, expected
            )
        elif opcode in {"ROL", "ROR"}:
            register, count = operands
            count = int(count)
            if count == 0:
                expected = (("MOV", (register, register)), ("NOP", ()))
            else:
                right_count = count if opcode == "ROR" else 32 - count
                expected = (("MOVS", ("r0", right_count)), ("ROR", (register, "r0")))
            cursor = _expect_sequence(
                fragment, cursor, main_size, image_base, decoded, expected
            )
        elif opcode == "CMP":
            left, right = operands
            cursor = _expect_sequence(
                fragment, cursor, main_size, image_base, decoded,
                (("MOV", ("r9", left)), ("MOV", ("r10", right))),
            )
        elif opcode in CONDITION_NAMES.values():
            target = _label_offset(fragment, str(operands[0]))
            cursor = _expect_sequence(
                fragment, cursor, main_size, image_base, decoded,
                (("CMP", ("r9", "r10")), (opcode, (image_base + int(target),))),
            )
        elif opcode == "BRA":
            target = _label_offset(fragment, str(operands[0]))
            cursor = _expect_sequence(
                fragment, cursor, main_size, image_base, decoded,
                (("B", (image_base + int(target),)), ("NOP", ())),
            )
        elif opcode == "EPILOGUE_RESTORE":
            cursor = _expect_one(
                fragment, cursor, main_size, image_base, decoded,
                "LDMIA", ("sp!",) + tuple(operands),
            )
        elif opcode == "RETURN":
            cursor = _expect_sequence(
                fragment, cursor, main_size, image_base, decoded,
                (("BX", ("lr",)), ("NOP", ())),
            )
        else:
            raise MachineAuditError(f"no independent audit rule for {opcode}")

    if cursor != main_size:
        raise MachineAuditError(
            f"backend plan ended at {cursor}, machine main body ends at {main_size}"
        )
    return tuple(decoded)


def audit_linked_helper_thunks(
    plans: tuple[Any, ...],
    fragment: Any,
    symbol_addresses: dict[str, int],
    *,
    image_base: int = 0,
) -> dict[int, tuple[DecodedInstruction, ...]]:
    """Decode each linked helper thunk and compare it with its thunk plan."""

    reports: dict[int, tuple[DecodedInstruction, ...]] = {}
    for plan in plans:
        label = f"@helper-thunk-{plan.call_site_offset:08x}"
        cursor = _label_offset(fragment, label)
        decoded: list[DecodedInstruction] = []
        for planned in plan.instructions:
            opcode = planned.opcode
            operands = planned.operands
            if opcode == "THUNK_ENTER_8":
                cursor = _expect_one(
                    fragment, cursor, len(fragment.code), image_base, decoded,
                    "STMDB", ("sp!",) + tuple(operands),
                )
            elif opcode == "THUNK_RETURN_8":
                cursor = _expect_one(
                    fragment, cursor, len(fragment.code), image_base, decoded,
                    "LDMIA", ("sp!",) + tuple(operands),
                )
            elif opcode == "MOV":
                cursor = _expect_one(
                    fragment, cursor, len(fragment.code), image_base, decoded,
                    "MOV", tuple(operands),
                )
            elif opcode == "MOV_IMM32":
                instruction = _decode_at(
                    fragment, cursor, len(fragment.code), image_base
                )
                if instruction.mnemonic != "LDR_LITERAL" or instruction.operands[0] != operands[0]:
                    raise MachineAuditError("thunk literal load does not match plan")
                _, value = _literal_value(
                    fragment, int(instruction.operands[1]), image_base
                )
                if value != int(operands[1]) & 0xFFFF_FFFF:
                    raise MachineAuditError("thunk literal value does not match plan")
                decoded.append(instruction)
                cursor += instruction.size
                cursor = _expect_one(
                    fragment, cursor, len(fragment.code), image_base, decoded, "NOP", ()
                )
            elif opcode == "BL":
                symbol = str(operands[0])
                target = _symbol_address(symbol_addresses, symbol)
                cursor = _expect_one(
                    fragment, cursor, len(fragment.code), image_base, decoded,
                    "BL", (target & ~1,),
                )
            elif opcode == "ABORT_IF_NONZERO":
                status, symbol, unwind = operands
                if status != "r0" or unwind != 8:
                    raise MachineAuditError("unsupported abort plan in helper thunk")
                start = cursor
                cursor = _expect_sequence(
                    fragment, cursor, len(fragment.code), image_base, decoded,
                    (
                        ("CMP_IMM", ("r0", 0)),
                        ("BEQ", (image_base + start + 12,)),
                        ("LDMIA", ("sp!", "r12", "lr")),
                        ("B.W", (_symbol_address(symbol_addresses, str(symbol)) & ~1,)),
                    ),
                )
            else:
                raise MachineAuditError(f"no independent thunk audit rule for {opcode}")
        reports[plan.call_site_offset] = tuple(decoded)
    return reports


def audit_private_abi_veneers(
    plans: tuple[Any, ...],
    image: Any,
    runtime_symbols: dict[str, int],
) -> dict[str, tuple[DecodedInstruction, ...]]:
    """Independently decode each private-ABI veneer and its alignment bytes."""

    if image.relocations or not image.link_complete or image.execution_authorized:
        raise MachineAuditError("private ABI veneer image is not sealed for audit")
    ordered = sorted(
        ((int(image.labels[plan.public_symbol]), plan) for plan in plans),
        key=lambda item: item[0],
    )
    reports: dict[str, tuple[DecodedInstruction, ...]] = {}
    for index, (start, plan) in enumerate(ordered):
        if start % 4:
            raise MachineAuditError("private ABI veneer symbol is not 4-byte aligned")
        end = ordered[index + 1][0] if index + 1 < len(ordered) else len(image.code)
        cursor = start
        decoded: list[DecodedInstruction] = []
        for planned in plan.instructions:
            opcode = planned.opcode
            operands = tuple(planned.operands)
            if opcode == "CALL_RUNTIME":
                expected = (
                    "BL",
                    (_symbol_address(runtime_symbols, plan.runtime_symbol) & ~1,),
                )
            elif opcode == "TAIL_RUNTIME":
                expected = (
                    "B.W",
                    (_symbol_address(runtime_symbols, plan.runtime_symbol) & ~1,),
                )
            elif opcode in {"STMDB", "LDMIA", "MOV", "PUSH", "POP", "BX"}:
                expected = (opcode, operands)
            elif opcode in {"LDR_SP", "STR_SP", "ADD_FROM_SP", "ADD_SP", "SUB_SP"}:
                expected = (opcode, operands)
            elif opcode == "NOP":
                expected = ("NOP", ())
            else:
                raise MachineAuditError(
                    f"no independent private ABI audit rule for {opcode}"
                )
            cursor = _expect_one(
                image, cursor, end, image.image_base, decoded, *expected
            )
        while cursor < end:
            cursor = _expect_one(
                image, cursor, end, image.image_base, decoded, "NOP", ()
            )
        if cursor != end:
            raise MachineAuditError("private ABI veneer crosses its symbol boundary")
        reports[plan.public_symbol] = tuple(decoded)
    if set(reports) != set(image.labels):
        raise MachineAuditError("private ABI veneer labels do not match audited plans")
    return reports


def _expect_one(
    fragment: Any,
    cursor: int,
    main_size: int,
    image_base: int,
    decoded: list[DecodedInstruction],
    mnemonic: str,
    operands: tuple[str | int, ...],
) -> int:
    instruction = _decode_at(fragment, cursor, main_size, image_base)
    if instruction.mnemonic != mnemonic or instruction.operands != operands:
        raise MachineAuditError(
            f"machine mismatch at {cursor}: expected {mnemonic} {operands}, "
            f"got {instruction.mnemonic} {instruction.operands}"
        )
    decoded.append(instruction)
    return cursor + instruction.size


def _expect_sequence(
    fragment: Any,
    cursor: int,
    main_size: int,
    image_base: int,
    decoded: list[DecodedInstruction],
    expected: tuple[tuple[str, tuple[str | int, ...]], ...],
) -> int:
    for mnemonic, operands in expected:
        cursor = _expect_one(
            fragment, cursor, main_size, image_base, decoded, mnemonic, operands
        )
    return cursor


def _decode_at(
    fragment: Any, cursor: int, main_size: int, image_base: int,
) -> DecodedInstruction:
    if cursor >= main_size:
        raise MachineAuditError("backend plan extends beyond machine main body")
    try:
        instruction = decode_thumb_instruction(
            fragment.code, cursor, image_base=image_base
        )
    except DisassemblyError as error:
        raise MachineAuditError(str(error)) from error
    if cursor + instruction.size > main_size:
        raise MachineAuditError("instruction crosses machine main boundary")
    return instruction


def _label_offset(fragment: Any, label: str) -> int:
    try:
        return int(fragment.labels[label])
    except KeyError as error:
        raise MachineAuditError(f"missing machine label {label}") from error


def _symbol_address(symbol_addresses: dict[str, int], symbol: str) -> int:
    try:
        value = int(symbol_addresses[symbol])
    except KeyError as error:
        raise MachineAuditError(f"missing machine symbol {symbol}") from error
    if not 0 <= value <= 0xFFFF_FFFF:
        raise MachineAuditError(f"machine symbol outside 32-bit range: {symbol}")
    return value


def _literal_value(
    fragment: Any, literal_address: int, image_base: int,
) -> tuple[int, int]:
    literal_offset = literal_address - image_base
    if literal_offset < 0 or literal_offset + 4 > len(fragment.code):
        raise MachineAuditError("literal load target is outside the fragment")
    return literal_offset, struct.unpack_from("<I", fragment.code, literal_offset)[0]


def _decoded(
    code: bytes,
    offset: int,
    size: int,
    mnemonic: str,
    operands: tuple[str | int, ...],
) -> DecodedInstruction:
    return DecodedInstruction(offset, size, mnemonic, operands, code[offset:offset + size])


def _second_halfword(code: bytes, offset: int) -> int:
    if offset + 4 > len(code):
        raise DisassemblyError("truncated Thumb-2 instruction")
    return struct.unpack_from("<H", code, offset + 2)[0]


def _register(number: int) -> str:
    return {13: "sp", 14: "lr", 15: "pc"}.get(number, f"r{number}")


def _register_list(mask: int) -> tuple[str, ...]:
    return tuple(_register(number) for number in range(16) if mask & (1 << number))


def _sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def _decode_wide_branch_displacement(first: int, second: int) -> int:
    sign = (first >> 10) & 1
    j1 = (second >> 13) & 1
    j2 = (second >> 11) & 1
    i1 = (~(j1 ^ sign)) & 1
    i2 = (~(j2 ^ sign)) & 1
    encoded = (
        (sign << 24)
        | (i1 << 23)
        | (i2 << 22)
        | ((first & 0x3FF) << 12)
        | ((second & 0x7FF) << 1)
    )
    return _sign_extend(encoded, 25)
