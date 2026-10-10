"""Incremental linker for guarded RP2350 Thumb fragments."""

from __future__ import annotations

from dataclasses import replace
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
