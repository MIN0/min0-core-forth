"""RP2350 private-ABI veneers for the portable runtime helper core.

The emitted Thumb bytes are linkable and independently auditable, but this
module does not grant execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import struct

from min0_rp2350_linker import encode_thumb_b_w, encode_thumb_bl
from min0_virtual_assembler import VerifyError
from min0_virtual_assembler_rp2350 import ARCHITECTURE, FUNCTION_FRAME_REGISTERS


NOP = 0xBF00
UDF_SLOT = struct.pack("<HH", 0xDE00, 0xDE01)


@dataclass(frozen=True)
class VeneerInstruction:
    opcode: str
    operands: tuple[str | int, ...] = ()


@dataclass(frozen=True)
class PrivateAbiVeneerPlan:
    public_symbol: str
    runtime_symbol: str
    instructions: tuple[VeneerInstruction, ...]


@dataclass(frozen=True)
class VeneerRelocation:
    offset: int
    opcode: str
    symbol: str


@dataclass(frozen=True)
class PrivateAbiVeneerImage:
    architecture: str
    code: bytes
    labels: dict[str, int]
    relocations: tuple[VeneerRelocation, ...]
    image_base: int = 0
    link_complete: bool = False
    execution_authorized: bool = False


def private_abi_veneer_plans() -> tuple[PrivateAbiVeneerPlan, ...]:
    """Return the fixed semantic plan that bridges private and ordinary ABI."""

    return (
        PrivateAbiVeneerPlan(
            "min0_frame_load", "min0_runtime_frame_load",
            (
                VeneerInstruction("PUSH", ("r2", "lr")),
                VeneerInstruction("MOV", ("r2", "sp")),
                VeneerInstruction("CALL_RUNTIME"),
                VeneerInstruction("LDR_SP", ("r1", 0)),
                VeneerInstruction("POP", ("r2", "pc")),
            ),
        ),
        PrivateAbiVeneerPlan(
            "min0_result_stage", "min0_runtime_result_stage",
            (VeneerInstruction("TAIL_RUNTIME"),),
        ),
        PrivateAbiVeneerPlan(
            "min0_checked_ld32", "min0_runtime_checked_ld32",
            (
                VeneerInstruction("PUSH", ("r1", "r2", "r3", "lr")),
                VeneerInstruction("SUB_SP", (8,)),
                VeneerInstruction("ADD_FROM_SP", ("r2", 4)),
                VeneerInstruction("STR_SP", ("r2", 0)),
                VeneerInstruction("LDR_SP", ("r2", 12)),
                VeneerInstruction("LDR_SP", ("r3", 16)),
                VeneerInstruction("CALL_RUNTIME"),
                VeneerInstruction("LDR_SP", ("r1", 4)),
                VeneerInstruction("ADD_SP", (12,)),
                VeneerInstruction("POP", ("r2", "r3", "pc")),
            ),
        ),
        PrivateAbiVeneerPlan(
            "min0_stage_st32", "min0_runtime_stage_st32",
            (
                VeneerInstruction("STMDB", ("sp!", "r12", "lr")),
                VeneerInstruction("CALL_RUNTIME"),
                VeneerInstruction("LDMIA", ("sp!", "r12", "pc")),
            ),
        ),
        PrivateAbiVeneerPlan(
            "min0_frame_commit", "min0_runtime_frame_commit",
            (VeneerInstruction("TAIL_RUNTIME"),),
        ),
        PrivateAbiVeneerPlan(
            "min0_abort_transaction", "min0_runtime_abort_transaction",
            (
                VeneerInstruction("MOV", ("r1", "r0")),
                VeneerInstruction("MOV", ("r0", "r8")),
                VeneerInstruction("CALL_RUNTIME"),
                VeneerInstruction("LDMIA", ("sp!",) + FUNCTION_FRAME_REGISTERS),
                VeneerInstruction("BX", ("lr",)),
                VeneerInstruction("NOP"),
            ),
        ),
    )


def emit_private_abi_veneers() -> PrivateAbiVeneerImage:
    code = bytearray()
    labels: dict[str, int] = {}
    relocations: list[VeneerRelocation] = []
    plans = private_abi_veneer_plans()
    verify_private_abi_veneer_plans(plans)
    for plan in plans:
        while len(code) % 4:
            code.extend(struct.pack("<H", NOP))
        labels[plan.public_symbol] = len(code)
        for instruction in plan.instructions:
            _emit_instruction(code, relocations, plan, instruction)
    return PrivateAbiVeneerImage(
        ARCHITECTURE, bytes(code), labels, tuple(relocations)
    )


def link_private_abi_veneers(
    image: PrivateAbiVeneerImage,
    *,
    image_base: int,
    runtime_symbols: dict[str, int],
) -> PrivateAbiVeneerImage:
    if image.architecture != ARCHITECTURE or image.link_complete:
        raise VerifyError("private ABI veneer image is not linkable")
    if image_base < 0 or image_base > 0xFFFF_FFFF or image_base % 4:
        raise VerifyError("private ABI veneer image base must be 4-byte aligned")
    code = bytearray(image.code)
    seen_offsets: set[int] = set()
    for relocation in image.relocations:
        if (
            relocation.opcode not in {"BL", "B.W"}
            or relocation.offset in seen_offsets
            or relocation.offset < 0
            or relocation.offset % 2
            or relocation.offset + 4 > len(code)
            or code[relocation.offset:relocation.offset + 4] != UDF_SLOT
        ):
            raise VerifyError("private ABI veneer has an invalid relocation")
        seen_offsets.add(relocation.offset)
        try:
            target = int(runtime_symbols[relocation.symbol]) & ~1
        except KeyError as error:
            raise VerifyError(
                f"no address for RP2350 runtime symbol {relocation.symbol}"
            ) from error
        if not 0 <= target <= 0xFFFF_FFFF:
            raise VerifyError(
                f"RP2350 runtime symbol outside 32-bit range: {relocation.symbol}"
            )
        source = image_base + relocation.offset
        encoder = encode_thumb_bl if relocation.opcode == "BL" else encode_thumb_b_w
        code[relocation.offset:relocation.offset + 4] = encoder(source, target)
    return PrivateAbiVeneerImage(
        image.architecture,
        bytes(code),
        dict(image.labels),
        (),
        image_base,
        True,
        False,
    )


def private_abi_symbol_addresses(
    image: PrivateAbiVeneerImage,
) -> dict[str, int]:
    if not image.link_complete:
        raise VerifyError("private ABI veneer image is not link complete")
    return {
        symbol: (image.image_base + offset) | 1
        for symbol, offset in image.labels.items()
    }


def verify_private_abi_veneer_plans(
    plans: tuple[PrivateAbiVeneerPlan, ...],
) -> None:
    expected = {
        "min0_frame_load",
        "min0_result_stage",
        "min0_checked_ld32",
        "min0_stage_st32",
        "min0_frame_commit",
        "min0_abort_transaction",
    }
    names = [plan.public_symbol for plan in plans]
    if len(names) != len(set(names)) or set(names) != expected:
        raise VerifyError("private ABI veneer symbol set is incomplete or duplicated")
    expected_runtime = {
        name: name.replace("min0_", "min0_runtime_", 1)
        for name in expected
    }
    for plan in plans:
        if plan.runtime_symbol != expected_runtime[plan.public_symbol]:
            raise VerifyError("private ABI veneer targets the wrong runtime symbol")
        calls = [
            item for item in plan.instructions
            if item.opcode in {"CALL_RUNTIME", "TAIL_RUNTIME"}
        ]
        if len(calls) != 1:
            raise VerifyError("each private ABI veneer must call one runtime symbol")
        stack_delta = 0
        for instruction in plan.instructions:
            stack_delta += _stack_effect(instruction)
            if instruction.opcode in {"CALL_RUNTIME", "TAIL_RUNTIME"}:
                if stack_delta % 8:
                    raise VerifyError("private ABI veneer calls C with a misaligned stack")
        expected_delta = 32 if plan.public_symbol == "min0_abort_transaction" else 0
        if stack_delta != expected_delta:
            raise VerifyError("private ABI veneer has an unbalanced CPU stack effect")
    by_name = {plan.public_symbol: plan for plan in plans}
    if by_name["min0_stage_st32"].instructions[0] != VeneerInstruction(
        "STMDB", ("sp!", "r12", "lr")
    ):
        raise VerifyError("ST32 veneer must place r12 in the fifth C argument slot")
    abort = by_name["min0_abort_transaction"].instructions
    if VeneerInstruction("LDMIA", ("sp!",) + FUNCTION_FRAME_REGISTERS) not in abort:
        raise VerifyError("abort veneer must restore the generated function frame")


def _stack_effect(instruction: VeneerInstruction) -> int:
    if instruction.opcode in {"PUSH", "STMDB"}:
        registers = instruction.operands[1:] if instruction.opcode == "STMDB" else instruction.operands
        return -4 * len(registers)
    if instruction.opcode in {"POP", "LDMIA"}:
        registers = instruction.operands[1:] if instruction.opcode == "LDMIA" else instruction.operands
        return 4 * len(registers)
    if instruction.opcode == "SUB_SP":
        return -int(instruction.operands[0])
    if instruction.opcode == "ADD_SP":
        return int(instruction.operands[0])
    return 0


def _emit_instruction(
    code: bytearray,
    relocations: list[VeneerRelocation],
    plan: PrivateAbiVeneerPlan,
    instruction: VeneerInstruction,
) -> None:
    op = instruction.opcode
    args = instruction.operands
    if op == "PUSH":
        code.extend(struct.pack("<H", _encode_push_pop(args, pop=False)))
    elif op == "POP":
        code.extend(struct.pack("<H", _encode_push_pop(args, pop=True)))
    elif op == "MOV":
        code.extend(struct.pack("<H", _encode_mov(*args)))
    elif op == "LDR_SP":
        code.extend(struct.pack("<H", _encode_sp_memory(*args, load=True)))
    elif op == "STR_SP":
        code.extend(struct.pack("<H", _encode_sp_memory(*args, load=False)))
    elif op == "ADD_FROM_SP":
        code.extend(struct.pack("<H", _encode_add_from_sp(*args)))
    elif op == "SUB_SP":
        code.extend(struct.pack("<H", _encode_adjust_sp(int(args[0]), subtract=True)))
    elif op == "ADD_SP":
        code.extend(struct.pack("<H", _encode_adjust_sp(int(args[0]), subtract=False)))
    elif op in {"CALL_RUNTIME", "TAIL_RUNTIME"}:
        offset = len(code)
        relocations.append(VeneerRelocation(
            offset, "BL" if op == "CALL_RUNTIME" else "B.W", plan.runtime_symbol
        ))
        code.extend(UDF_SLOT)
    elif op in {"STMDB", "LDMIA"}:
        load = op == "LDMIA"
        code.extend(_encode_wide_stack(args, load=load))
    elif op == "BX":
        if args != ("lr",):
            raise VerifyError("private ABI veneer only supports BX lr")
        code.extend(struct.pack("<H", 0x4770))
    elif op == "NOP":
        code.extend(struct.pack("<H", NOP))
    else:
        raise VerifyError(f"cannot emit private ABI veneer opcode {op}")


def _register_number(name: str) -> int:
    aliases = {"sp": 13, "lr": 14, "pc": 15}
    if name in aliases:
        return aliases[name]
    if name.startswith("r") and name[1:].isdigit():
        number = int(name[1:])
        if 0 <= number <= 12:
            return number
    raise VerifyError(f"unknown private ABI veneer register {name}")


def _encode_mov(destination: str | int, source: str | int) -> int:
    destination_number = _register_number(str(destination))
    source_number = _register_number(str(source))
    if destination_number > 12 or source_number > 14:
        raise VerifyError("unsupported private ABI veneer MOV register")
    return (
        0x4600
        | ((destination_number & 8) << 4)
        | (source_number << 3)
        | (destination_number & 7)
    )


def _encode_push_pop(registers: tuple[str | int, ...], *, pop: bool) -> int:
    mask = 0
    special = "pc" if pop else "lr"
    for raw in registers:
        name = str(raw)
        if name == special:
            mask |= 1 << 8
            continue
        number = _register_number(name)
        if number > 7:
            raise VerifyError("Thumb PUSH/POP veneer register must be low")
        mask |= 1 << number
    return (0xBC00 if pop else 0xB400) | mask


def _encode_sp_memory(
    register: str | int, offset: str | int, *, load: bool,
) -> int:
    number = _register_number(str(register))
    offset = int(offset)
    if number > 7 or offset < 0 or offset % 4 or offset > 1020:
        raise VerifyError("invalid private ABI SP-relative memory operand")
    return (0x9800 if load else 0x9000) | (number << 8) | (offset // 4)


def _encode_add_from_sp(register: str | int, offset: str | int) -> int:
    number = _register_number(str(register))
    offset = int(offset)
    if number > 7 or offset < 0 or offset % 4 or offset > 1020:
        raise VerifyError("invalid private ABI ADD-from-SP operand")
    return 0xA800 | (number << 8) | (offset // 4)


def _encode_adjust_sp(amount: int, *, subtract: bool) -> int:
    if amount <= 0 or amount % 4 or amount > 508:
        raise VerifyError("invalid private ABI SP adjustment")
    return (0xB080 if subtract else 0xB000) | (amount // 4)


def _encode_wide_stack(
    operands: tuple[str | int, ...], *, load: bool,
) -> bytes:
    if not operands or operands[0] != "sp!":
        raise VerifyError("private ABI wide stack operation requires sp!")
    mask = 0
    for raw in operands[1:]:
        mask |= 1 << _register_number(str(raw))
    return struct.pack("<HH", 0xE8BD if load else 0xE92D, mask)
