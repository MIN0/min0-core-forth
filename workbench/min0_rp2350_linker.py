"""Incremental linker for guarded RP2350 Thumb fragments."""

from __future__ import annotations

from dataclasses import dataclass, replace
import struct

from min0_rp2350_thumb_emitter import (
    MachineFragment,
    MachineRelocation,
    UDF_RELOCATION_SLOT,
    REGISTER_NUMBER,
    verify_machine_fragment,
)
from min0_virtual_assembler import VerifyError
from min0_virtual_assembler_rp2350 import HELPER_SIGNATURES


NOP = 0xBF00


@dataclass(frozen=True)
class ThunkInstruction:
    opcode: str
    operands: tuple[str | int, ...]


@dataclass(frozen=True)
class HelperThunkPlan:
    call_site_offset: int
    helper_symbol: str
    instructions: tuple[ThunkInstruction, ...]


def link_literal_constants(fragment: MachineFragment) -> MachineFragment:
    """Resolve MOV_IMM32 actions through a deduplicated trailing literal pool."""

    verify_machine_fragment(fragment)
    targets = [item for item in fragment.relocations if item.opcode == "MOV_IMM32"]
    if not targets:
        return fragment

    code = bytearray(fragment.code)
    while len(code) % 4:
        code.extend(b"\x00\xBF")
    pool_start = len(code)
    value_offsets: dict[int, int] = {}
    for relocation in targets:
        value = int(relocation.operands[1]) & 0xFFFF_FFFF
        if value not in value_offsets:
            value_offsets[value] = len(code)
            code.extend(struct.pack("<I", value))

    remaining: list[MachineRelocation] = []
    for relocation in fragment.relocations:
        if relocation.opcode != "MOV_IMM32":
            remaining.append(relocation)
            continue
        register_name = str(relocation.operands[0])
        register = REGISTER_NUMBER.get(register_name, 16)
        if register > 7:
            raise VerifyError("Thumb literal load requires a low destination register")
        value = int(relocation.operands[1]) & 0xFFFF_FFFF
        literal_offset = value_offsets[value]
        pc_base = (relocation.offset + 4) & ~3
        displacement = literal_offset - pc_base
        if displacement < 0 or displacement % 4 or displacement > 1020:
            raise VerifyError("literal pool is outside Thumb LDR literal range")
        halfword = 0x4800 | (register << 8) | (displacement // 4)
        code[relocation.offset:relocation.offset + 4] = struct.pack("<HH", halfword, NOP)

    linked = MachineFragment(
        fragment.architecture, bytes(code), tuple(remaining), dict(fragment.labels)
    )
    verify_machine_fragment(linked)
    if pool_start >= len(linked.code):
        raise VerifyError("literal linker did not append a pool")
    return linked


def bind_helper_symbols(fragment: MachineFragment) -> MachineFragment:
    """Bind helper backend actions to named out-of-line thunk relocations."""

    verify_machine_fragment(fragment)
    relocations: list[MachineRelocation] = []
    for relocation in fragment.relocations:
        signature = HELPER_SIGNATURES.get(relocation.opcode)
        if signature is None:
            relocations.append(relocation)
            continue
        relocations.append(replace(
            relocation,
            kind="RP2350_HELPER_THUNK_CALL",
            symbol=signature.name,
        ))
    bound = MachineFragment(
        fragment.architecture, fragment.code, tuple(relocations), dict(fragment.labels)
    )
    verify_machine_fragment(bound)
    return bound


def prepare_link(fragment: MachineFragment) -> MachineFragment:
    """Apply every linker pass that is safe without final addresses."""

    return bind_helper_symbols(link_literal_constants(fragment))


def plan_helper_thunks(
    fragment: MachineFragment, capability_ids: dict[str, int],
) -> tuple[HelperThunkPlan, ...]:
    """Build auditable, 8-byte CPU-stack-balanced helper thunk plans."""

    verify_machine_fragment(fragment)
    plans: list[HelperThunkPlan] = []
    for relocation in fragment.relocations:
        if relocation.kind != "RP2350_HELPER_THUNK_CALL":
            continue
        if relocation.symbol is None:
            raise VerifyError("helper thunk relocation has no symbol")
        body = [ThunkInstruction("THUNK_ENTER_8", ("r12", "lr"))]
        body.append(ThunkInstruction("MOV", ("r0", "r8")))
        if relocation.opcode == "CHECKED_LD32":
            destination, capability, base, offset = relocation.operands
            capability_id = _capability_id(str(capability), capability_ids)
            body.extend((
                ThunkInstruction("MOV_IMM32", ("r1", capability_id)),
                ThunkInstruction("MOV", ("r2", base)),
                ThunkInstruction("MOV_IMM32", ("r3", int(offset))),
                ThunkInstruction("BL", (relocation.symbol,)),
                ThunkInstruction(
                    "ABORT_IF_NONZERO", ("r0", "min0_abort_transaction", 8)
                ),
                ThunkInstruction("MOV", (destination, "r1")),
            ))
        elif relocation.opcode == "STAGE_ST32":
            capability, base, offset, source = relocation.operands
            capability_id = _capability_id(str(capability), capability_ids)
            body.extend((
                ThunkInstruction("MOV_IMM32", ("r1", capability_id)),
                ThunkInstruction("MOV", ("r2", base)),
                ThunkInstruction("MOV_IMM32", ("r3", int(offset))),
                ThunkInstruction("MOV", ("r12", source)),
                ThunkInstruction("BL", (relocation.symbol,)),
                ThunkInstruction(
                    "ABORT_IF_NONZERO", ("r0", "min0_abort_transaction", 8)
                ),
            ))
        elif relocation.opcode == "FRAME_COMMIT":
            input_count, output_count = relocation.operands
            body.extend((
                ThunkInstruction("MOV_IMM32", ("r1", int(input_count))),
                ThunkInstruction("MOV_IMM32", ("r2", int(output_count))),
                ThunkInstruction("BL", (relocation.symbol,)),
                ThunkInstruction(
                    "ABORT_IF_NONZERO", ("r0", "min0_abort_transaction", 8)
                ),
            ))
        else:
            raise VerifyError(f"unsupported helper thunk {relocation.opcode}")
        body.append(ThunkInstruction("THUNK_RETURN_8", ("r12", "pc")))
        plan = HelperThunkPlan(relocation.offset, relocation.symbol, tuple(body))
        verify_helper_thunk(plan)
        plans.append(plan)
    return tuple(plans)


def verify_helper_thunk(plan: HelperThunkPlan) -> None:
    if not plan.instructions:
        raise VerifyError("empty helper thunk")
    if plan.instructions[0] != ThunkInstruction("THUNK_ENTER_8", ("r12", "lr")):
        raise VerifyError("helper thunk must enter with an 8-byte CPU stack frame")
    if plan.instructions[-1] != ThunkInstruction("THUNK_RETURN_8", ("r12", "pc")):
        raise VerifyError("helper thunk must return and release its 8-byte CPU stack frame")
    forbidden = {"PUSH_DATA", "POP_DATA", "RAW_LDR", "RAW_STR"}
    if any(item.opcode in forbidden for item in plan.instructions):
        raise VerifyError("helper thunk touches forbidden state")
    calls = [item for item in plan.instructions if item.opcode == "BL"]
    if len(calls) != 1 or calls[0].operands != (plan.helper_symbol,):
        raise VerifyError("helper thunk must call exactly its bound helper")
    aborts = [item for item in plan.instructions if item.opcode == "ABORT_IF_NONZERO"]
    if len(aborts) != 1 or aborts[0].operands[2] != 8:
        raise VerifyError("helper failure path must unwind the 8-byte CPU stack frame")


def _capability_id(name: str, capability_ids: dict[str, int]) -> int:
    try:
        value = capability_ids[name]
    except KeyError as error:
        raise VerifyError(f"no numeric ID for memory capability {name}") from error
    if not 0 <= value <= 0xFFFF_FFFF:
        raise VerifyError(f"memory capability ID outside 32-bit range: {name}")
    return value
